"""Parsing orchestration service."""

import asyncio
from concurrent.futures import ProcessPoolExecutor
from functools import partial

from sqlalchemy.ext.asyncio import AsyncSession

from code_parser.config import get_settings
from code_parser.core import ParsedFile, RepositoryStatus
from code_parser.logging import get_logger
from code_parser.parsers import get_parser_registry
from code_parser.repositories import FileRepository, RepoRepository, SymbolRepository
from code_parser.services.file_discovery import (
    DiscoveredFile,
    build_folder_structure,
    build_repo_tree,
    discover_files,
    read_file_content,
    validate_repo_tree,
)

logger = get_logger(__name__)


def _parse_file_in_process(
    file_path: str,
    relative_path: str,
) -> ParsedFile | None:
    """
    Parse a single file (runs in separate process).
    
    This function is designed to be called via ProcessPoolExecutor
    for CPU-bound parsing work.
    """
    try:
        registry = get_parser_registry()
        parser = registry.get_parser_for_file(relative_path)

        if not parser:
            return None

        content, content_hash = read_file_content(file_path)
        return parser.parse(content, relative_path, content_hash)

    except Exception as e:
        # Return a ParsedFile with error
        from code_parser.core import Language, ParsedFile

        lang = Language.from_extension(relative_path.rsplit(".", 1)[-1]) or Language.PYTHON
        return ParsedFile(
            relative_path=relative_path,
            language=lang,
            content_hash="",
            symbols=(),
            references=(),
            errors=(str(e),),
        )


class ParsingService:
    """
    Orchestrates the parsing of entire repositories.
    
    Handles file discovery, parallel parsing, and database persistence.
    """

    def __init__(
        self,
        session: AsyncSession,
        max_workers: int | None = None,
    ) -> None:
        self._session = session
        self._settings = get_settings()
        self._max_workers = max_workers or self._settings.worker_count
        self._repo_repository = RepoRepository(session)
        self._file_repository = FileRepository(session)
        self._symbol_repository = SymbolRepository(session)

    async def parse_repository(self, repo_id: str) -> None:
        """
        Parse an entire repository.
        
        Updates the repository status throughout the process
        and persists all parsed symbols and references.
        """
        logger.info("parsing_started", repo_id=repo_id)

        repo = await self._repo_repository.get_by_id(repo_id)
        if not repo:
            raise ValueError(f"Repository not found: {repo_id}")

        try:
            # Update status to parsing
            await self._repo_repository.update_status(repo_id, RepositoryStatus.PARSING)
            await self._session.commit()

            # Discover files
            files = discover_files(repo.root_path)
            total_files = len(files)

            # Build repository tree structure
            repo_tree = build_repo_tree(files)
            
            # Validate repo_tree structure
            if not validate_repo_tree(repo_tree):
                logger.warning("invalid_repo_tree", repo_id=repo_id, tree_type=type(repo_tree).__name__)
                repo_tree = {}
            
            await self._repo_repository.update_repo_tree(repo_id, repo_tree)
            logger.info(
                "repo_tree_updated",
                repo_id=repo_id,
                file_count=total_files,
                tree_valid=validate_repo_tree(repo_tree),
            )
            
            await self._repo_repository.update_progress(repo_id, total_files, 0)
            await self._session.commit()

            # Parse files in parallel
            parsed_count = 0
            batch_size = self._settings.max_files_per_batch
            detected_languages: set[str] = set()

            for i in range(0, total_files, batch_size):
                batch = files[i : i + batch_size]
                parsed_files = await self._parse_batch(batch)

                # Persist parsed results
                for discovered, parsed in zip(batch, parsed_files):
                    if parsed and not parsed.has_errors:
                        # Track detected languages
                        detected_languages.add(parsed.language.value)
                        
                        # Build folder structure for this file
                        folder_structure = build_folder_structure(
                            discovered.relative_path, files
                        )
                        await self._persist_parsed_file(
                            repo_id, parsed, folder_structure, discovered.absolute_path
                        )
                        parsed_count += 1
                    elif parsed and parsed.has_errors:
                        logger.warning(
                            "file_parse_errors",
                            path=discovered.relative_path,
                            errors=parsed.errors,
                        )

                # Update progress
                await self._repo_repository.update_progress(
                    repo_id, total_files, min(i + batch_size, total_files)
                )
                await self._session.commit()
            
            # Update detected languages
            if detected_languages:
                await self._repo_repository.update_languages(
                    repo_id, sorted(list(detected_languages))
                )
                await self._session.commit()

            # Resolve cross-file references
            resolved_count = await self._symbol_repository.resolve_cross_file_references(
                repo_id
            )
            logger.info(
                "cross_file_references_resolved",
                repo_id=repo_id,
                resolved_count=resolved_count,
            )

            # Mark as completed
            await self._repo_repository.update_status(repo_id, RepositoryStatus.COMPLETED)
            await self._session.commit()

            logger.info(
                "parsing_completed",
                repo_id=repo_id,
                total_files=total_files,
                parsed_files=parsed_count,
            )

        except Exception as e:
            logger.exception("parsing_failed", repo_id=repo_id, error=str(e))
            await self._session.rollback()
            await self._repo_repository.update_status(
                repo_id, RepositoryStatus.FAILED, error_message=str(e)
            )
            await self._session.commit()
            raise

    async def _parse_batch(
        self, files: list[DiscoveredFile]
    ) -> list[ParsedFile | None]:
        """Parse a batch of files in parallel using process pool."""
        loop = asyncio.get_event_loop()

        with ProcessPoolExecutor(max_workers=self._max_workers) as executor:
            tasks = [
                loop.run_in_executor(
                    executor,
                    partial(
                        _parse_file_in_process,
                        f.absolute_path,
                        f.relative_path,
                    ),
                )
                for f in files
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to None
        parsed: list[ParsedFile | None] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(
                    "file_parse_exception",
                    path=files[i].relative_path,
                    error=str(result),
                )
                parsed.append(None)
            else:
                parsed.append(result)

        return parsed

    async def _persist_parsed_file(
        self, repo_id: str, parsed: ParsedFile, folder_structure: dict, absolute_path: str
    ) -> None:
        """Persist a parsed file's symbols and references."""
        # Validate parsed file
        if not parsed.relative_path:
            logger.warning("invalid_parsed_file", reason="missing_relative_path")
            return
        
        if not parsed.content_hash:
            logger.warning("invalid_parsed_file", reason="missing_content_hash", path=parsed.relative_path)
            return
        
        # Read file content to store
        content = None
        try:
            with open(absolute_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Validate content hash matches
            from code_parser.services.file_discovery import compute_file_hash
            actual_hash = compute_file_hash(content.encode('utf-8'))
            if actual_hash != parsed.content_hash:
                logger.warning(
                    "content_hash_mismatch",
                    path=parsed.relative_path,
                    expected=parsed.content_hash,
                    actual=actual_hash,
                )
        except Exception as e:
            # If we can't read the file, log warning but continue
            logger.warning(
                "failed_to_read_file_content",
                path=parsed.relative_path,
                absolute_path=absolute_path,
                error=str(e),
            )
        
        # Upsert file record
        try:
            file_id = await self._file_repository.upsert(
                repo_id=repo_id,
                relative_path=parsed.relative_path,
                language=parsed.language,
                content_hash=parsed.content_hash,
                content=content,
                folder_structure=folder_structure,
            )
        except Exception as e:
            logger.error(
                "failed_to_persist_file",
                path=parsed.relative_path,
                error=str(e),
            )
            raise

        # Bulk insert symbols and references
        try:
            await self._symbol_repository.bulk_insert_from_parsed_file(
                repo_id=repo_id,
                file_id=file_id,
                parsed_file=parsed,
            )
        except Exception as e:
            logger.error(
                "failed_to_persist_symbols",
                path=parsed.relative_path,
                file_id=file_id,
                error=str(e),
            )
            raise

    async def should_reparse_file(
        self, repo_id: str, relative_path: str, new_hash: str
    ) -> bool:
        """Check if a file needs to be reparsed based on content hash."""
        existing_hash = await self._file_repository.get_content_hash(
            repo_id, relative_path
        )
        return existing_hash != new_hash

