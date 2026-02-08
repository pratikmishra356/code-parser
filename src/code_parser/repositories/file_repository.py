"""Repository for managing parsed files."""

from ulid import ULID
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from code_parser.core import Language
from code_parser.database.models import FileModel


class FileRepository:
    """Data access layer for File entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self,
        repo_id: str,
        relative_path: str,
        language: Language,
        content_hash: str,
        content: str | None = None,
        folder_structure: dict | None = None,
    ) -> str:
        """
        Insert or update a file record.
        
        Args:
            repo_id: Repository ID
            relative_path: File path relative to repo root
            language: Programming language
            content_hash: SHA-256 hash of file content
            content: File source code content
            folder_structure: Folder structure for this file's parent directory
            
        Returns the file ID.
        """
        # Check if file exists
        result = await self._session.execute(
            select(FileModel).where(
                FileModel.repo_id == repo_id,
                FileModel.relative_path == relative_path,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.content_hash = content_hash
            existing.language = language.value
            if content is not None:
                existing.content = content
            if folder_structure is not None:
                existing.folder_structure = folder_structure
            await self._session.flush()
            return existing.id

        # Create new file
        file_id = str(ULID())
        model = FileModel(
            id=file_id,
            repo_id=repo_id,
            relative_path=relative_path,
            language=language.value,
            content_hash=content_hash,
            content=content,
            folder_structure=folder_structure,
        )
        self._session.add(model)
        await self._session.flush()
        return file_id

    async def get_by_id(self, file_id: str) -> FileModel | None:
        """Get file by ID."""
        result = await self._session.execute(
            select(FileModel).where(FileModel.id == file_id)
        )
        return result.scalar_one_or_none()

    async def get_content_hash(self, repo_id: str, relative_path: str) -> str | None:
        """Get the content hash for a file (for incremental parsing)."""
        result = await self._session.execute(
            select(FileModel.content_hash).where(
                FileModel.repo_id == repo_id,
                FileModel.relative_path == relative_path,
            )
        )
        row = result.one_or_none()
        return row[0] if row else None

    async def list_by_repo(
        self, repo_id: str, limit: int = 1000, offset: int = 0
    ) -> list[FileModel]:
        """List all files in a repository."""
        result = await self._session.execute(
            select(FileModel)
            .where(FileModel.repo_id == repo_id)
            .order_by(FileModel.relative_path)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars())

    async def list_by_repo_with_search(
        self,
        repo_id: str,
        search: str | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[FileModel]:
        """
        List files in a repo with optional regex search on relative_path.
        """
        query = select(FileModel).where(FileModel.repo_id == repo_id)

        if search:
            query = query.where(FileModel.relative_path.op("~*")(search))

        query = query.order_by(FileModel.relative_path).limit(limit).offset(offset)
        result = await self._session.execute(query)
        return list(result.scalars())

    async def delete_by_repo(self, repo_id: str) -> int:
        """Delete all files for a repository. Returns count deleted."""
        result = await self._session.execute(
            delete(FileModel).where(FileModel.repo_id == repo_id)
        )
        return result.rowcount

