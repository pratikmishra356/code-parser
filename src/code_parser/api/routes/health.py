"""Health check endpoints."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from code_parser import __version__
from code_parser.api.dependencies import DbSession
from code_parser.api.schemas import HealthResponse
from code_parser.workers import WorkerManager

router = APIRouter(tags=["health"])

# Reference to worker manager (set by app startup)
_worker_manager: WorkerManager | None = None


def set_worker_manager(manager: WorkerManager) -> None:
    """Set the worker manager reference for health checks."""
    global _worker_manager
    _worker_manager = manager


@router.get("/health", response_model=HealthResponse)
async def health_check(session: DbSession) -> HealthResponse:
    """
    Health check endpoint.
    
    Returns the status of the service, database connectivity,
    and worker status.
    """
    # Check database
    try:
        await session.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {e}"

    # Check workers
    worker_status = {
        "running": _worker_manager.is_running if _worker_manager else False,
    }

    overall_status = "healthy" if db_status == "healthy" else "degraded"

    return HealthResponse(
        status=overall_status,
        version=__version__,
        database=db_status,
        workers=worker_status,
    )


@router.get("/ready")
async def readiness_check(session: DbSession) -> dict:
    """
    Readiness probe for Kubernetes.
    
    Returns 200 if the service is ready to accept traffic.
    """
    try:
        await session.execute(text("SELECT 1"))
        return {"ready": True}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database not ready: {e}")


@router.get("/live")
async def liveness_check() -> dict:
    """
    Liveness probe for Kubernetes.
    
    Returns 200 if the service is alive.
    """
    return {"alive": True}

