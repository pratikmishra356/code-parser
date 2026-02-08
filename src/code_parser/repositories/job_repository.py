"""Repository for managing parsing jobs (PostgreSQL-based queue)."""

from datetime import datetime

from ulid import ULID
from sqlalchemy import text, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from code_parser.core import ParsingJob, RepositoryStatus
from code_parser.database.models import ParsingJobModel


class JobRepository:
    """
    Data access layer for the parsing job queue.
    
    Uses PostgreSQL's FOR UPDATE SKIP LOCKED for safe concurrent
    job claiming without external queue infrastructure.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, repo_id: str) -> ParsingJob:
        """Create a new parsing job."""
        job_id = str(ULID())
        model = ParsingJobModel(
            id=job_id,
            repo_id=repo_id,
            status=RepositoryStatus.PENDING.value,
        )
        self._session.add(model)
        await self._session.flush()

        return self._to_domain(model)

    async def claim_next(self, worker_id: str) -> ParsingJob | None:
        """
        Atomically claim the next pending job.
        
        Uses FOR UPDATE SKIP LOCKED to safely handle concurrent
        workers without conflicts.
        """
        result = await self._session.execute(
            text("""
                UPDATE parsing_jobs
                SET status = 'parsing',
                    started_at = NOW(),
                    worker_id = :worker_id
                WHERE id = (
                    SELECT id FROM parsing_jobs
                    WHERE status = 'pending'
                    ORDER BY created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                RETURNING id, repo_id, status, worker_id, error_message,
                          created_at, started_at, completed_at
            """),
            {"worker_id": worker_id},
        )

        row = result.fetchone()
        if not row:
            return None

        return ParsingJob(
            id=row.id,
            repo_id=row.repo_id,
            status=RepositoryStatus(row.status),
            created_at=row.created_at,
            started_at=row.started_at,
            completed_at=row.completed_at,
            worker_id=row.worker_id,
            error_message=row.error_message,
        )

    async def mark_completed(self, job_id: str) -> None:
        """Mark a job as successfully completed."""
        await self._session.execute(
            update(ParsingJobModel)
            .where(ParsingJobModel.id == job_id)
            .values(
                status=RepositoryStatus.COMPLETED.value,
                completed_at=datetime.utcnow(),
            )
        )

    async def mark_failed(self, job_id: str, error_message: str) -> None:
        """Mark a job as failed with error message."""
        await self._session.execute(
            update(ParsingJobModel)
            .where(ParsingJobModel.id == job_id)
            .values(
                status=RepositoryStatus.FAILED.value,
                completed_at=datetime.utcnow(),
                error_message=error_message,
            )
        )

    async def get_by_id(self, job_id: str) -> ParsingJob | None:
        """Get job by ID."""
        result = await self._session.execute(
            select(ParsingJobModel).where(ParsingJobModel.id == job_id)
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_pending_count(self) -> int:
        """Get count of pending jobs."""
        result = await self._session.execute(
            text("SELECT COUNT(*) FROM parsing_jobs WHERE status = 'pending'")
        )
        return result.scalar() or 0

    async def get_running_count(self) -> int:
        """Get count of running jobs."""
        result = await self._session.execute(
            text("SELECT COUNT(*) FROM parsing_jobs WHERE status = 'parsing'")
        )
        return result.scalar() or 0

    def _to_domain(self, model: ParsingJobModel) -> ParsingJob:
        """Convert ORM model to domain entity."""
        return ParsingJob(
            id=model.id,
            repo_id=model.repo_id,
            status=RepositoryStatus(model.status),
            created_at=model.created_at,
            started_at=model.started_at,
            completed_at=model.completed_at,
            worker_id=model.worker_id,
            error_message=model.error_message,
        )

