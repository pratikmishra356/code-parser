"""Background worker manager for processing parsing jobs."""

import asyncio
import uuid
from datetime import datetime

from code_parser.config import get_settings
from code_parser.database.connection import get_session_manager
from code_parser.logging import get_logger
from code_parser.repositories import JobRepository, RepoRepository
from code_parser.services import ParsingService

logger = get_logger(__name__)


class WorkerManager:
    """
    Manages background workers that process parsing jobs.
    
    Workers poll the PostgreSQL job queue using SKIP LOCKED
    for safe concurrent job claiming.
    """

    def __init__(self, num_workers: int | None = None) -> None:
        self._settings = get_settings()
        self._num_workers = num_workers or self._settings.worker_count
        self._workers: list[asyncio.Task] = []
        self._shutdown_event = asyncio.Event()
        self._instance_id = str(uuid.uuid4())[:8]

    async def start(self) -> None:
        """Start all worker tasks."""
        logger.info(
            "worker_manager_starting",
            num_workers=self._num_workers,
            instance_id=self._instance_id,
        )

        for i in range(self._num_workers):
            worker_id = f"{self._instance_id}-worker-{i}"
            task = asyncio.create_task(
                self._worker_loop(worker_id),
                name=worker_id,
            )
            self._workers.append(task)

        logger.info("worker_manager_started", num_workers=len(self._workers))

    async def stop(self) -> None:
        """Gracefully stop all workers."""
        logger.info("worker_manager_stopping")

        # Signal shutdown
        self._shutdown_event.set()

        # Wait for workers to finish current job
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)

        logger.info("worker_manager_stopped")

    async def _worker_loop(self, worker_id: str) -> None:
        """
        Main worker loop - polls for and processes jobs.
        
        Uses exponential backoff when no jobs are available.
        """
        logger.info("worker_started", worker_id=worker_id)
        poll_interval = self._settings.job_poll_interval_seconds
        backoff_multiplier = 1.0

        while not self._shutdown_event.is_set():
            try:
                job = await self._try_claim_job(worker_id)

                if job:
                    backoff_multiplier = 1.0  # Reset backoff
                    await self._process_job(job, worker_id)
                else:
                    # No jobs available - wait with backoff
                    wait_time = poll_interval * backoff_multiplier
                    backoff_multiplier = min(backoff_multiplier * 1.5, 10.0)

                    try:
                        await asyncio.wait_for(
                            self._shutdown_event.wait(),
                            timeout=wait_time,
                        )
                    except asyncio.TimeoutError:
                        pass  # Normal timeout, continue polling

            except Exception as e:
                logger.exception(
                    "worker_error",
                    worker_id=worker_id,
                    error=str(e),
                )
                # Wait before retrying after error
                await asyncio.sleep(poll_interval * 2)

        logger.info("worker_stopped", worker_id=worker_id)

    async def _try_claim_job(self, worker_id: str):
        """Try to claim the next pending job."""
        session_manager = get_session_manager()

        async with session_manager.session() as session:
            job_repository = JobRepository(session)
            job = await job_repository.claim_next(worker_id)
            return job

    async def _process_job(self, job, worker_id: str) -> None:
        """Process a claimed job."""
        logger.info(
            "job_processing_started",
            job_id=job.id,
            repo_id=job.repo_id,
            worker_id=worker_id,
        )
        start_time = datetime.utcnow()

        session_manager = get_session_manager()

        try:
            async with session_manager.session() as session:
                # Create services with this session
                parsing_service = ParsingService(session)
                job_repository = JobRepository(session)

                # Process the repository
                await parsing_service.parse_repository(job.repo_id)

                # Mark job as completed
                await job_repository.mark_completed(job.id)

            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                "job_processing_completed",
                job_id=job.id,
                repo_id=job.repo_id,
                worker_id=worker_id,
                duration_seconds=duration,
            )

        except Exception as e:
            logger.exception(
                "job_processing_failed",
                job_id=job.id,
                repo_id=job.repo_id,
                worker_id=worker_id,
                error=str(e),
            )

            # Mark job as failed
            async with session_manager.session() as session:
                job_repository = JobRepository(session)
                await job_repository.mark_failed(job.id, str(e))

    @property
    def is_running(self) -> bool:
        """Check if workers are running."""
        return len(self._workers) > 0 and not self._shutdown_event.is_set()

