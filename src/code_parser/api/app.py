"""FastAPI application factory."""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from code_parser import __version__
from code_parser.api.routes import (
    entry_points_router,
    explore_router,
    graph_router,
    health_router,
    orgs_router,
    repositories_router,
    symbols_router,
)
from code_parser.api.routes.health import set_worker_manager
from code_parser.config import get_settings
from code_parser.database.connection import init_database, get_session_manager
from code_parser.logging import configure_logging, get_logger
from code_parser.workers import WorkerManager

logger = get_logger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    # Configure logging first
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Application lifespan handler for startup/shutdown."""
        logger.info("application_starting", version=__version__)

        # Initialize database
        init_database()

        # Start background workers
        worker_manager = WorkerManager()
        set_worker_manager(worker_manager)
        await worker_manager.start()

        yield

        # Shutdown
        logger.info("application_stopping")
        await worker_manager.stop()
        await get_session_manager().close()
        logger.info("application_stopped")

    app = FastAPI(
        title="Code Parser API",
        description="Production-grade code parsing service with AST analysis and call graph generation",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health_router)
    app.include_router(repositories_router, prefix="/api/v1")
    app.include_router(symbols_router, prefix="/api/v1")
    app.include_router(graph_router, prefix="/api/v1")
    app.include_router(entry_points_router, prefix="/api/v1")
    # Multi-tenancy and explore APIs
    app.include_router(orgs_router, prefix="/api/v1")
    app.include_router(explore_router, prefix="/api/v1")

    logger.info(
        "application_configured",
        debug=settings.debug,
        worker_count=settings.worker_count,
    )

    return app

