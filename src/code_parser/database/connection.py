"""Database connection management with async SQLAlchemy."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from code_parser.config import get_settings
from code_parser.logging import get_logger

logger = get_logger(__name__)


class DatabaseSessionManager:
    """
    Manages database connections and sessions.
    
    Provides async context managers for obtaining database sessions
    with proper connection pooling and cleanup.
    """

    def __init__(self, database_url: str) -> None:
        self._engine: AsyncEngine = create_async_engine(
            database_url,
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Provide a transactional scope around a series of operations.
        
        Commits on success, rolls back on exception.
        """
        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    @asynccontextmanager
    async def readonly_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Provide a read-only session (no commit)."""
        session = self._session_factory()
        try:
            yield session
        finally:
            await session.close()

    async def close(self) -> None:
        """Close all connections in the pool."""
        await self._engine.dispose()
        logger.info("database_connection_closed")

    @property
    def engine(self) -> AsyncEngine:
        """Get the underlying engine (for migrations, etc.)."""
        return self._engine


# Global session manager instance (initialized on startup)
_session_manager: DatabaseSessionManager | None = None


def init_database(database_url: str | None = None) -> DatabaseSessionManager:
    """Initialize the global database session manager."""
    global _session_manager
    url = database_url or str(get_settings().database_url)
    _session_manager = DatabaseSessionManager(url)
    logger.info("database_initialized", url=url.split("@")[-1])  # Log without credentials
    return _session_manager


def get_session_manager() -> DatabaseSessionManager:
    """Get the global session manager. Raises if not initialized."""
    if _session_manager is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _session_manager


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for getting a database session."""
    async with get_session_manager().session() as session:
        yield session

