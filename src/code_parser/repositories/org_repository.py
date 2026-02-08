"""Repository for managing organizations."""

from ulid import ULID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from code_parser.core import Organization
from code_parser.database.models import OrganizationModel


class OrgRepository:
    """Data access layer for Organization entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, name: str, description: str | None = None) -> Organization:
        """Create a new organization."""
        org_id = str(ULID())
        model = OrganizationModel(
            id=org_id,
            name=name,
            description=description,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_domain(model)

    async def get_by_id(self, org_id: str) -> Organization | None:
        """Get organization by ID."""
        result = await self._session.execute(
            select(OrganizationModel).where(OrganizationModel.id == org_id)
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_by_name(self, name: str) -> Organization | None:
        """Get organization by name."""
        result = await self._session.execute(
            select(OrganizationModel).where(OrganizationModel.name == name)
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def list_all(
        self, limit: int = 100, offset: int = 0
    ) -> list[Organization]:
        """List all organizations with pagination."""
        result = await self._session.execute(
            select(OrganizationModel)
            .order_by(OrganizationModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [self._to_domain(model) for model in result.scalars()]

    async def delete(self, org_id: str) -> bool:
        """Delete an organization and all associated data (cascades)."""
        result = await self._session.execute(
            select(OrganizationModel).where(OrganizationModel.id == org_id)
        )
        model = result.scalar_one_or_none()
        if model:
            await self._session.delete(model)
            return True
        return False

    def _to_domain(self, model: OrganizationModel) -> Organization:
        """Convert ORM model to domain entity."""
        return Organization(
            id=model.id,
            name=model.name,
            description=model.description,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
