"""Repository for managing code repositories."""

from ulid import ULID
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from code_parser.core import Repository, RepositoryStatus
from code_parser.database.models import RepositoryModel


class RepoRepository:
    """Data access layer for Repository entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, name: str, root_path: str, org_id: str) -> Repository:
        """Create a new repository record."""
        repo_id = str(ULID())
        model = RepositoryModel(
            id=repo_id,
            name=name,
            root_path=root_path,
            org_id=org_id,
            status=RepositoryStatus.PENDING.value,
        )
        self._session.add(model)
        await self._session.flush()

        return self._to_domain(model)

    async def get_by_id(self, repo_id: str) -> Repository | None:
        """Get repository by ID."""
        result = await self._session.execute(
            select(RepositoryModel).where(RepositoryModel.id == repo_id)
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_by_id_and_org(self, repo_id: str, org_id: str) -> Repository | None:
        """Get repository by ID scoped to an organization."""
        result = await self._session.execute(
            select(RepositoryModel).where(
                RepositoryModel.id == repo_id,
                RepositoryModel.org_id == org_id,
            )
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_by_path(self, root_path: str, org_id: str | None = None) -> Repository | None:
        """Get repository by root path, optionally scoped to an org."""
        query = select(RepositoryModel).where(RepositoryModel.root_path == root_path)
        if org_id:
            query = query.where(RepositoryModel.org_id == org_id)
        result = await self._session.execute(query)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def list_all(
        self, limit: int = 100, offset: int = 0
    ) -> list[Repository]:
        """List all repositories with pagination."""
        result = await self._session.execute(
            select(RepositoryModel)
            .order_by(RepositoryModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [self._to_domain(model) for model in result.scalars()]

    async def list_by_org(
        self,
        org_id: str,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Repository]:
        """
        List repositories for an organization with optional regex search.
        
        Args:
            org_id: Organization ID
            search: Optional regex pattern to match against name or description
            limit: Maximum results
            offset: Pagination offset
        """
        query = (
            select(RepositoryModel)
            .where(RepositoryModel.org_id == org_id)
        )

        if search:
            # Use PostgreSQL ~ operator for regex matching on name and description
            query = query.where(
                or_(
                    RepositoryModel.name.op("~*")(search),
                    RepositoryModel.description.op("~*")(search),
                )
            )

        query = query.order_by(RepositoryModel.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(query)
        return [self._to_domain(model) for model in result.scalars()]

    async def update_status(
        self,
        repo_id: str,
        status: RepositoryStatus,
        error_message: str | None = None,
    ) -> None:
        """Update repository status."""
        values: dict = {"status": status.value}
        if error_message is not None:
            values["error_message"] = error_message

        await self._session.execute(
            update(RepositoryModel)
            .where(RepositoryModel.id == repo_id)
            .values(**values)
        )

    async def update_progress(
        self, repo_id: str, total_files: int, parsed_files: int
    ) -> None:
        """Update parsing progress counters."""
        await self._session.execute(
            update(RepositoryModel)
            .where(RepositoryModel.id == repo_id)
            .values(total_files=total_files, parsed_files=parsed_files)
        )

    async def update_repo_tree(self, repo_id: str, repo_tree: dict) -> None:
        """Update the repository tree structure."""
        await self._session.execute(
            update(RepositoryModel)
            .where(RepositoryModel.id == repo_id)
            .values(repo_tree=repo_tree)
        )

    async def update_languages(self, repo_id: str, languages: list[str]) -> None:
        """Update the detected languages for the repository."""
        await self._session.execute(
            update(RepositoryModel)
            .where(RepositoryModel.id == repo_id)
            .values(languages=languages)
        )

    async def update_description(self, repo_id: str, description: str) -> None:
        """Update the repository description."""
        await self._session.execute(
            update(RepositoryModel)
            .where(RepositoryModel.id == repo_id)
            .values(description=description)
        )

    async def delete(self, repo_id: str) -> bool:
        """Delete a repository and all associated data (cascades)."""
        result = await self._session.execute(
            select(RepositoryModel).where(RepositoryModel.id == repo_id)
        )
        model = result.scalar_one_or_none()
        if model:
            await self._session.delete(model)
            return True
        return False

    def _to_domain(self, model: RepositoryModel) -> Repository:
        """Convert ORM model to domain entity."""
        return Repository(
            id=model.id,
            name=model.name,
            root_path=model.root_path,
            status=RepositoryStatus(model.status),
            org_id=model.org_id,
            description=model.description,
            total_files=model.total_files,
            parsed_files=model.parsed_files,
            created_at=model.created_at,
            updated_at=model.updated_at,
            error_message=model.error_message,
            languages=model.languages or [],
            repo_tree=model.repo_tree,
        )

