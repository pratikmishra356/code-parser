"""Repository for managing entry point candidates and confirmed entry points."""

from datetime import datetime
from typing import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from code_parser.core import ConfirmedEntryPoint, EntryPointCandidate, EntryPointType
from code_parser.database.models import EntryPointCandidateModel, EntryPointModel


class EntryPointRepository:
    """Data access layer for EntryPoint entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bulk_insert_candidates(
        self, repo_id: str, candidates: Sequence[EntryPointCandidate]
    ) -> None:
        """
        Bulk insert entry point candidates.
        
        Args:
            repo_id: Repository ID
            candidates: List of entry point candidates to insert
        """
        for candidate in candidates:
            model = EntryPointCandidateModel(
                id=str(ULID()),
                repo_id=repo_id,
                symbol_id=candidate.symbol_id,
                file_id=candidate.file_id,
                entry_point_type=candidate.entry_point_type.value,
                framework=candidate.framework,
                detection_pattern=candidate.detection_pattern,
                entry_metadata=candidate.metadata,
                confidence_score=candidate.confidence_score,
            )
            self._session.add(model)

        await self._session.flush()

    async def bulk_insert_confirmed(
        self, repo_id: str, confirmed: Sequence[ConfirmedEntryPoint]
    ) -> None:
        """
        Bulk insert confirmed entry points.
        
        Args:
            repo_id: Repository ID
            confirmed: List of confirmed entry points to insert
        """
        for entry_point in confirmed:
            model = EntryPointModel(
                id=str(ULID()),
                repo_id=repo_id,
                symbol_id=entry_point.symbol_id,
                file_id=entry_point.file_id,
                entry_point_type=entry_point.entry_point_type.value,
                framework=entry_point.framework,
                name=entry_point.name,
                description=entry_point.description,
                entry_metadata=entry_point.metadata,
                ai_confidence=entry_point.ai_confidence,
                ai_reasoning=entry_point.ai_reasoning,
            )
            self._session.add(model)

        await self._session.flush()

    async def get_by_repo(self, repo_id: str) -> list[EntryPointModel]:
        """Get all confirmed entry points for a repository."""
        result = await self._session.execute(
            select(EntryPointModel).where(EntryPointModel.repo_id == repo_id)
        )
        return list(result.scalars().all())

    async def list_by_repo_with_search(
        self,
        repo_id: str,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EntryPointModel]:
        """
        List entry points for a repo with optional regex search on name/description.
        """
        from sqlalchemy import or_
        query = select(EntryPointModel).where(EntryPointModel.repo_id == repo_id)

        if search:
            query = query.where(
                or_(
                    EntryPointModel.name.op("~*")(search),
                    EntryPointModel.description.op("~*")(search),
                )
            )

        query = query.order_by(EntryPointModel.detected_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_by_ids(
        self, repo_id: str, entry_point_ids: list[str]
    ) -> list[EntryPointModel]:
        """Get multiple entry points by their IDs."""
        if not entry_point_ids:
            return []
        result = await self._session.execute(
            select(EntryPointModel).where(
                EntryPointModel.repo_id == repo_id,
                EntryPointModel.id.in_(entry_point_ids),
            )
        )
        return list(result.scalars().all())

    async def get_by_type(
        self, repo_id: str, entry_point_type: EntryPointType
    ) -> list[EntryPointModel]:
        """Get entry points by type for a repository."""
        result = await self._session.execute(
            select(EntryPointModel).where(
                EntryPointModel.repo_id == repo_id,
                EntryPointModel.entry_point_type == entry_point_type.value,
            )
        )
        return list(result.scalars().all())

    async def get_by_framework(
        self, repo_id: str, framework: str
    ) -> list[EntryPointModel]:
        """Get entry points by framework for a repository."""
        result = await self._session.execute(
            select(EntryPointModel).where(
                EntryPointModel.repo_id == repo_id,
                EntryPointModel.framework == framework,
            )
        )
        return list(result.scalars().all())

    async def get_by_id(
        self, repo_id: str, entry_point_id: str
    ) -> EntryPointModel | None:
        """Get a specific entry point by ID."""
        result = await self._session.execute(
            select(EntryPointModel).where(
                EntryPointModel.id == entry_point_id,
                EntryPointModel.repo_id == repo_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_candidates_by_repo(
        self, repo_id: str
    ) -> list[EntryPointCandidateModel]:
        """Get all candidates for a repository."""
        result = await self._session.execute(
            select(EntryPointCandidateModel).where(
                EntryPointCandidateModel.repo_id == repo_id
            )
        )
        return list(result.scalars().all())

    async def delete_by_repo(self, repo_id: str) -> None:
        """
        Delete all entry points and candidates for a repository.
        
        Used for re-detection.
        """
        await self._session.execute(
            delete(EntryPointModel).where(EntryPointModel.repo_id == repo_id)
        )
        await self._session.execute(
            delete(EntryPointCandidateModel).where(
                EntryPointCandidateModel.repo_id == repo_id
            )
        )
        await self._session.flush()
