"""Service for detecting entry points using Tree-sitter queries and AI confirmation."""

from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from code_parser.core import (
    ConfirmedEntryPoint,
    EntryPointCandidate,
    EntryPointType,
    Language,
)
from code_parser.database.models import FileModel, RepositoryModel, SymbolModel
from code_parser.entry_points.query_executor import QueryExecutor, QueryMatch
from code_parser.entry_points.queries import (
    java_queries,
    javascript_queries,
    kotlin_queries,
    python_queries,
    rust_queries,
)
from code_parser.logging import get_logger
from code_parser.parsers.registry import get_parser_registry
from code_parser.repositories.entry_point_repository import EntryPointRepository
from code_parser.repositories.file_repository import FileRepository
from code_parser.repositories.repo_repository import RepoRepository
from code_parser.repositories.symbol_repository import SymbolRepository
from code_parser.services.ai_service import AIService

logger = get_logger(__name__)


class EntryPointService:
    """Service for detecting and confirming entry points."""

    def __init__(
        self,
        session: AsyncSession,
        entry_point_repo: EntryPointRepository,
        file_repo: FileRepository,
        repo_repo: RepoRepository,
        symbol_repo: SymbolRepository,
    ) -> None:
        self._session = session
        self._entry_point_repo = entry_point_repo
        self._file_repo = file_repo
        self._repo_repo = repo_repo
        self._symbol_repo = symbol_repo
        self._parser_registry = get_parser_registry()
        self._ai_service = AIService()

    async def detect_entry_points(
        self, repo_id: str, force_redetect: bool = False
    ) -> dict[str, Any]:
        """
        Detect entry points for a repository.
        
        Args:
            repo_id: Repository ID
            force_redetect: If True, delete existing entry points and re-detect
            
        Returns:
            Dictionary with detection statistics
        """
        # Check if repository exists
        repo = await self._repo_repo.get_by_id(repo_id)
        if not repo:
            raise ValueError(f"Repository not found: {repo_id}")

        # Delete existing if force_redetect
        if force_redetect:
            await self._entry_point_repo.delete_by_repo(repo_id)
            await self._session.commit()

        # Get all files for repository
        files = await self._file_repo.list_by_repo(repo_id, limit=10000)
        logger.info("entry_point_detection_started", repo_id=repo_id, file_count=len(files))

        # STEP 1: Get potential candidates using Tree-sitter (run ALL queries on ALL files)
        tree_sitter_candidates, tree_sitter_file_paths = await self._step1_tree_sitter_detection(
            repo_id, files
        )
        
        logger.info(
            "step1_tree_sitter_complete",
            repo_id=repo_id,
            candidates_count=len(tree_sitter_candidates),
            files_with_candidates=len(tree_sitter_file_paths),
        )

        # STEP 2: AI analyzes repo structure and suggests potential file paths
        ai_suggested_file_paths = await self._step2_ai_file_path_detection(
            repo_id, repo
        )
        
        logger.info(
            "step2_ai_file_paths_complete",
            repo_id=repo_id,
            ai_suggested_paths=len(ai_suggested_file_paths),
        )

        # STEP 3: Union file paths from step 1 and 2, then AI confirmation in batches
        all_file_paths = tree_sitter_file_paths | ai_suggested_file_paths
        
        # Get files for unioned paths
        files_to_analyze = {
            f.relative_path: f for f in files 
            if f.relative_path in all_file_paths
        }
        
        logger.info(
            "step3_union_complete",
            repo_id=repo_id,
            total_file_paths=len(all_file_paths),
            tree_sitter_paths=len(tree_sitter_file_paths),
            ai_suggested_paths=len(ai_suggested_file_paths),
            files_to_analyze=len(files_to_analyze),
        )

        # Store Tree-sitter candidates
        if tree_sitter_candidates:
            await self._entry_point_repo.bulk_insert_candidates(repo_id, tree_sitter_candidates)
            await self._session.commit()

        # Build symbol contexts for all files to analyze
        all_candidates_for_ai = tree_sitter_candidates.copy()
        symbol_contexts = await self._build_symbol_contexts_for_files(
            repo_id, list(files_to_analyze.values())
        )

        # Confirm with AI in batches of 10
        repo_context = {
            "languages": repo.languages or [],
            "repo_tree": repo.repo_tree,
        }

        # Define callback to store confirmed entry points after each batch
        async def store_batch_confirmed(batch_confirmed: list, batch_index: int) -> None:
            """Store confirmed entry points after each batch."""
            if batch_confirmed:
                await self._entry_point_repo.bulk_insert_confirmed(repo_id, batch_confirmed)
                await self._session.commit()
                logger.info(
                    "batch_confirmed_stored",
                    repo_id=repo_id,
                    batch_index=batch_index,
                    confirmed_count=len(batch_confirmed),
                )

        confirmed = await self._ai_service.confirm_entry_points_from_files(
            files_to_analyze,
            repo_context,
            symbol_contexts,
            batch_size=10,
            on_batch_confirmed=store_batch_confirmed,
        )

        logger.info(
            "entry_point_confirmation_complete",
            repo_id=repo_id,
            confirmed_count=len(confirmed),
            candidate_count=len(all_candidates),
        )

        # Build statistics
        stats = self._build_statistics(confirmed)

        return {
            "candidates_detected": len(all_candidates),
            "entry_points_confirmed": len(confirmed),
            "frameworks_detected": list(detected_frameworks),
            "statistics": stats,
        }

    async def _detect_for_file(
        self, repo_id: str, file_model: FileModel
    ) -> tuple[list[EntryPointCandidate], set[str]]:
        """Detect entry point candidates for a single file."""
        if not file_model.content:
            return [], set()

        # Get parser for file language
        language = Language(file_model.language)
        parser = self._parser_registry.get_parser(language)
        if not parser:
            return [], set()

        # Create query executor
        query_executor = QueryExecutor(parser._language, parser._parser)

        # Detect frameworks from imports (simplified - extract from content)
        imports = self._extract_imports(file_model.content, language)
        frameworks = FrameworkDetector.detect_frameworks(language, imports)
        
        # Also detect Apache Camel via code patterns using Tree-sitter (generic, repo-agnostic)
        # This catches files that extend RouteBuilder classes (any package) without requiring direct imports
        if language == Language.KOTLIN:
            # Query 1: Find classes that extend something with "RouteBuilder" in the name
            route_builder_inheritance_query = """
            (class_declaration
              (delegation_specifier
                (type_identifier) @superclass_name))
            """
            # Query 2: Find configure() methods in classes
            configure_method_query = """
            (class_declaration
              (class_body
                (function_declaration
                  name: (identifier) @method_name)))
            """
            try:
                # Check for RouteBuilder inheritance
                inheritance_matches = query_executor.execute_query(
                    file_model.content, route_builder_inheritance_query, "route_builder_inheritance"
                )
                has_route_builder_inheritance = False
                for match in inheritance_matches:
                    superclass_node = match.captures.get("superclass_name")
                    if superclass_node:
                        superclass_name = query_executor.extract_node_text(
                            superclass_node, file_model.content
                        ).lower()
                        if "routebuilder" in superclass_name or "route_builder" in superclass_name:
                            has_route_builder_inheritance = True
                            break
                
                # Check for configure() method
                configure_matches = query_executor.execute_query(
                    file_model.content, configure_method_query, "configure_method_check"
                )
                has_configure_method = False
                for match in configure_matches:
                    method_node = match.captures.get("method_name")
                    if method_node:
                        method_name = query_executor.extract_node_text(
                            method_node, file_model.content
                        ).lower()
                        if method_name == "configure":
                            has_configure_method = True
                            break
                
                # If both conditions met, it's likely a Camel route
                if has_route_builder_inheritance and has_configure_method:
                    frameworks.add("apache-camel")
                    logger.info(
                        "camel_detected_via_code_pattern",
                        repo_id=repo_id,
                        file_path=file_model.relative_path,
                    )
            except Exception as e:
                # If query fails, log but don't fail - framework detection from imports is still primary
                logger.debug(
                    "route_builder_query_failed",
                    repo_id=repo_id,
                    file_path=file_model.relative_path,
                    error=str(e),
                )
        
        if imports or frameworks:
            logger.info(
                "framework_detection",
                repo_id=repo_id,
                file_path=file_model.relative_path,
                imports=list(imports),
                frameworks=list(frameworks),
            )

        # Get queries for detected frameworks
        query_names = FrameworkDetector.get_entry_point_queries_for_frameworks(
            language, frameworks
        )
        
        if query_names:
            logger.info(
                "queries_selected",
                repo_id=repo_id,
                file_path=file_model.relative_path,
                query_names=list(query_names),
            )

        # Get actual query strings
        queries = self._get_queries_for_language(language, query_names)

        # Execute queries
        matches_by_query = query_executor.execute_queries(file_model.content, queries)
        
        total_matches = sum(len(matches) for matches in matches_by_query.values())
        if total_matches > 0:
            logger.info(
                "query_execution_results",
                repo_id=repo_id,
                file_path=file_model.relative_path,
                matches_count={name: len(matches) for name, matches in matches_by_query.items()},
            )

        # Extract candidates from matches
        candidates: list[EntryPointCandidate] = []
        for query_name, matches in matches_by_query.items():
            for match in matches:
                # Filter camel_from_call to only match actual "from()" calls
                # Also filter camel_configure_method to only match "configure()" methods
                if query_name == "camel_from_call":
                    from_method_node = match.captures.get("from_method")
                    if from_method_node:
                        method_name = query_executor.extract_node_text(
                            from_method_node, file_model.content or ""
                        )
                        if method_name != "from":
                            continue  # Skip non-"from" calls
                elif query_name == "camel_configure_method":
                    function_name_node = match.captures.get("function_name")
                    if function_name_node:
                        function_name = query_executor.extract_node_text(
                            function_name_node, file_model.content or ""
                        )
                        if function_name != "configure":
                            continue  # Skip non-"configure" methods
                elif query_name == "camel_route_builder_class":
                    configure_method_node = match.captures.get("configure_method")
                    if configure_method_node:
                        method_name = query_executor.extract_node_text(
                            configure_method_node, file_model.content or ""
                        )
                        if method_name != "configure":
                            continue  # Skip classes without configure() method
                
                candidate = await self._extract_candidate(
                    repo_id, file_model, match, query_name, language, query_executor
                )
                if candidate:
                    candidates.append(candidate)

        return candidates, frameworks

    def _extract_imports(self, source_code: str, language: Language) -> set[str]:
        """Extract import/module names from source code."""
        imports: set[str] = set()
        lines = source_code.split("\n")

        for line in lines:
            line = line.strip()
            if language == Language.PYTHON:
                if line.startswith("import "):
                    # Extract full module name (e.g., "flask" from "import flask" or "flask" from "import flask.route")
                    module = line[7:].split()[0]
                    # Add both full module and first part
                    imports.add(module.split(".")[0])
                    imports.add(module)  # Also add full module for submodules
                elif line.startswith("from "):
                    # Extract module name (e.g., "flask" from "from flask import ...")
                    module = line[5:].split()[0]
                    imports.add(module.split(".")[0])
                    imports.add(module)  # Also add full module
            elif language in (Language.JAVA, Language.KOTLIN):
                if line.startswith("import "):
                    # Extract full package name (e.g., "org.apache.camel" from "import org.apache.camel.builder.RouteBuilder;")
                    module = line[7:].split(";")[0].strip()
                    if module and not module.startswith("static"):
                        # Remove wildcard imports
                        if module.endswith(".*"):
                            module = module[:-2]
                        # Add full package and all prefixes for matching
                        parts = module.split(".")
                        for i in range(1, len(parts) + 1):
                            imports.add(".".join(parts[:i]))
            elif language == Language.JAVASCRIPT:
                if "require(" in line or "import " in line:
                    # Extract module name (simplified)
                    if "from " in line:
                        module = line.split("from")[1].strip().split()[0].strip("'\"")
                        imports.add(module.split("/")[0])
                        imports.add(module)  # Also add full module
                    elif "require(" in line:
                        module = line.split("require(")[1].split(")")[0].strip("'\"")
                        imports.add(module.split("/")[0])
                        imports.add(module)  # Also add full module

        return imports

    def _get_queries_for_language(
        self, language: Language, query_names: set[str]
    ) -> dict[str, str]:
        """Get query strings for a language and set of query names."""
        if language == Language.PYTHON:
            all_queries = python_queries.get_python_queries()
        elif language == Language.JAVA:
            all_queries = java_queries.get_java_queries()
        elif language == Language.KOTLIN:
            all_queries = kotlin_queries.get_kotlin_queries()
        elif language == Language.JAVASCRIPT:
            all_queries = javascript_queries.get_javascript_queries()
        elif language == Language.RUST:
            all_queries = rust_queries.get_rust_queries()
        else:
            return {}
        
        return {name: all_queries[name] for name in query_names if name in all_queries}

    async def _extract_candidate(
        self,
        repo_id: str,
        file_model: FileModel,
        match: "QueryMatch",
        query_name: str,
        language: Language,
        query_executor: QueryExecutor,
    ) -> EntryPointCandidate | None:
        """Extract an EntryPointCandidate from a query match."""
        # Extract function/class name from captures (try multiple capture names in priority order)
        function_name_node = (
            match.captures.get("function_name")
            or match.captures.get("configure_method")
            or match.captures.get("execute_method")
            or match.captures.get("from_method")  # For camel_from_call
            or match.captures.get("http_method")  # For Ktor routes
        )
        
        class_name_node = match.captures.get("class_name")
        
        # Determine which symbol to look for
        symbol = None
        function_name = None
        
        # Priority 1: Function/method name (most specific)
        if function_name_node:
            function_name = query_executor.extract_node_text(
                function_name_node, file_model.content or ""
            )
            if function_name:
                symbol = await self._find_symbol_by_name_async(
                    repo_id, file_model.id, function_name
                )
                if not symbol:
                    # Try to find by position if available
                    start_line, end_line, _, _ = query_executor.extract_node_position(
                        function_name_node
                    )
                    if start_line:
                        symbol = await self._find_symbol_by_position(
                            repo_id, file_model.id, start_line
                        )
        
        # Priority 2: Class name (for class-based entry points like Camel routes)
        if not symbol and class_name_node:
            class_name = query_executor.extract_node_text(
                class_name_node, file_model.content or ""
            )
            if class_name:
                symbol = await self._find_symbol_by_name_async(
                    repo_id, file_model.id, class_name
                )
                # For Camel routes, prefer the configure() method if it exists
                if symbol and query_name.startswith("camel_"):
                    configure_symbol = await self._find_symbol_by_name_async(
                        repo_id, file_model.id, "configure"
                    )
                    if configure_symbol:
                        symbol = configure_symbol
                        function_name = "configure"

        if not symbol:
            logger.debug(
                "symbol_not_found_for_candidate",
                repo_id=repo_id,
                file_path=file_model.relative_path,
                function_name=function_name or "unknown",
                query_name=query_name,
            )
            return None

        # Determine entry point type and framework from query name
        entry_point_type, framework = self._infer_type_and_framework(query_name)

        # Extract metadata from captures
        metadata = self._extract_metadata(match, language, query_executor, file_model.content or "")

        return EntryPointCandidate(
            symbol_id=symbol.id,
            file_id=file_model.id,
            entry_point_type=entry_point_type,
            framework=framework,
            detection_pattern=query_name,
            metadata=metadata,
            confidence_score=0.8,  # Default confidence, can be improved
        )

    async def _find_symbol_by_name_async(
        self, repo_id: str, file_id: str, name: str
    ) -> SymbolModel | None:
        """Find a symbol by name in a file."""
        result = await self._session.execute(
            select(SymbolModel).where(
                SymbolModel.repo_id == repo_id,
                SymbolModel.file_id == file_id,
                SymbolModel.name == name,
            )
        )
        return result.scalar_one_or_none()

    async def _find_symbol_by_position(
        self, repo_id: str, file_id: str, start_line: int
    ) -> SymbolModel | None:
        """Find a symbol by position in a file."""
        result = await self._session.execute(
            select(SymbolModel).where(
                SymbolModel.repo_id == repo_id,
                SymbolModel.file_id == file_id,
                SymbolModel.start_line == start_line,
            )
        )
        return result.scalar_one_or_none()

    def _should_skip_file(self, file_path: str) -> bool:
        """
        Check if a file should be skipped for entry point detection.
        
        Filters out:
        - Test files (in test directories or with test naming patterns)
        - Base/abstract classes (common naming patterns)
        - Configuration/setup modules (DI setup, not routes)
        """
        file_path_lower = file_path.lower()
        filename = file_path.split("/")[-1].lower()
        
        # Test files - check directory path and filename
        if any(pattern in file_path_lower for pattern in [
            "/test/", "/tests/", "/it/", "/integration/",
            "test.kt", "test.java", "test.py", "test.js", "test.rs",
            "_test.", ".spec.", "spec.kt", "spec.js"
        ]):
            return True
        
        # Base/abstract classes - check filename patterns
        if any(pattern in filename for pattern in [
            "base", "abstract", "baseclass", "baseroute"
        ]):
            # Check if it's in a base directory (more likely to be a base class)
            if "/base/" in file_path_lower:
                return True
            # If filename contains "base" but it's a route file, allow it
            if "route" in filename and "base" in filename:
                return True
        
        # Configuration/setup modules - very specific patterns
        # Only filter if it's clearly a DI/config module, not a route
        if "module" in filename and not "route" in filename:
            # Check if it's a dependency injection module (common patterns)
            if any(pattern in file_path_lower for pattern in [
                "/module/", "/config/", "/di/", "/dependency/", "/setup/"
            ]):
                return True
        
        return False

    def _infer_type_and_framework(
        self, query_name: str
    ) -> tuple[EntryPointType, str]:
        """Infer entry point type and framework from query name."""
        # Apache Camel routes - these are event-driven (consume from Pulsar, Kafka, etc.)
        if "camel" in query_name:
            return EntryPointType.EVENT, "apache-camel"
        
        # HTTP endpoints
        if any(x in query_name for x in ["flask", "fastapi", "django", "route", "api_view"]):
            if "flask" in query_name:
                return EntryPointType.HTTP, "flask"
            elif "fastapi" in query_name:
                return EntryPointType.HTTP, "fastapi"
            elif "django" in query_name:
                return EntryPointType.HTTP, "django"
            return EntryPointType.HTTP, "unknown"

        # Event handlers
        if any(x in query_name for x in ["kafka", "pulsar", "celery", "consumer", "subscribe"]):
            if "kafka" in query_name:
                return EntryPointType.EVENT, "kafka"
            elif "pulsar" in query_name:
                return EntryPointType.EVENT, "pulsar"
            elif "celery" in query_name:
                return EntryPointType.EVENT, "celery"
            return EntryPointType.EVENT, "unknown"

        # Schedulers
        if any(x in query_name for x in ["scheduled", "cron", "scheduler"]):
            return EntryPointType.SCHEDULER, "scheduler"

        return EntryPointType.HTTP, "unknown"

    def _extract_metadata(
        self, match: "QueryMatch", language: Language, query_executor: QueryExecutor, source_code: str
    ) -> dict[str, Any]:
        """Extract metadata from query match captures."""
        metadata: dict[str, Any] = {}

        # Extract path if available
        path_node = match.captures.get("path")
        if path_node:
            path = query_executor.extract_node_text(path_node, source_code).strip('"\'')
            metadata["path"] = path

        # Extract HTTP method if available
        method_node = match.captures.get("method")
        if method_node:
            method = query_executor.extract_node_text(method_node, source_code).lower()
            metadata["method"] = method

        # Extract topic/event name for event handlers
        topic_node = match.captures.get("topic")
        if topic_node:
            topic = query_executor.extract_node_text(topic_node, source_code).strip('"\'')
            metadata["topic"] = topic

        # Extract schedule for schedulers
        schedule_node = match.captures.get("schedule_value") or match.captures.get(
            "cron_expression"
        )
        if schedule_node:
            schedule = query_executor.extract_node_text(schedule_node, source_code).strip('"\'')
            metadata["schedule"] = schedule

        return metadata

    async def _build_symbol_contexts(
        self, repo_id: str, candidates: list[EntryPointCandidate]
    ) -> dict[str, dict[str, Any]]:
        """Build symbol context dictionaries for AI prompts."""
        contexts: dict[str, dict[str, Any]] = {}

        for candidate in candidates:
            # Get symbol from database
            result = await self._session.execute(
                select(SymbolModel).where(SymbolModel.id == candidate.symbol_id)
            )
            symbol = result.scalar_one_or_none()
            if not symbol:
                continue

            # Get file for language and full file content
            file_result = await self._session.execute(
                select(FileModel).where(FileModel.id == candidate.file_id)
            )
            file_model = file_result.scalar_one_or_none()

            contexts[candidate.symbol_id] = {
                "name": symbol.name,
                "qualified_name": symbol.qualified_name,
                "signature": symbol.signature or "",
                "source_code": symbol.source_code,  # Symbol-specific code
                "file_path": file_model.relative_path if file_model else "unknown",
                "file_content": file_model.content if file_model else "",  # Full file content
                "language": file_model.language if file_model else "unknown",
            }

        return contexts

    def _build_statistics(
        self, confirmed: list[ConfirmedEntryPoint]
    ) -> dict[str, Any]:
        """Build statistics from confirmed entry points."""
        stats: dict[str, Any] = {
            "by_type": defaultdict(int),
            "by_framework": defaultdict(int),
        }

        for ep in confirmed:
            stats["by_type"][ep.entry_point_type.value] += 1
            stats["by_framework"][ep.framework] += 1

        return {
            "by_type": dict(stats["by_type"]),
            "by_framework": dict(stats["by_framework"]),
        }
