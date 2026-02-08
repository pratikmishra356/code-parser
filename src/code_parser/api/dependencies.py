"""FastAPI dependency injection."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from code_parser.database.connection import get_session_manager
from code_parser.repositories import (
    EntryPointRepository,
    FileRepository,
    JobRepository,
    RepoRepository,
    SymbolRepository,
)
from code_parser.repositories.flow_repository import FlowRepository
from code_parser.services import AIService, FlowService, GraphService, ParsingService


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting a database session."""
    async with get_session_manager().session() as session:
        yield session


# Type aliases for dependency injection
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_repo_repository(session: DbSession) -> RepoRepository:
    """Dependency for RepoRepository."""
    return RepoRepository(session)


def get_file_repository(session: DbSession) -> FileRepository:
    """Dependency for FileRepository."""
    return FileRepository(session)


def get_symbol_repository(session: DbSession) -> SymbolRepository:
    """Dependency for SymbolRepository."""
    return SymbolRepository(session)


def get_job_repository(session: DbSession) -> JobRepository:
    """Dependency for JobRepository."""
    return JobRepository(session)


def get_parsing_service(session: DbSession) -> ParsingService:
    """Dependency for ParsingService."""
    return ParsingService(session)


def get_graph_service(session: DbSession) -> GraphService:
    """Dependency for GraphService."""
    return GraphService(session)


def get_entry_point_repository(session: DbSession) -> EntryPointRepository:
    """Dependency for EntryPointRepository."""
    return EntryPointRepository(session)


def get_flow_repository(session: DbSession) -> FlowRepository:
    """Dependency for FlowRepository."""
    return FlowRepository(session)


def get_flow_service(
    session: DbSession,
    flow_repo: FlowRepository = Depends(get_flow_repository),
    entry_point_repo: EntryPointRepository = Depends(get_entry_point_repository),
    symbol_repo: SymbolRepository = Depends(get_symbol_repository),
    file_repo: FileRepository = Depends(get_file_repository),
    graph_service: GraphService = Depends(get_graph_service),
) -> FlowService:
    """Dependency for FlowService."""
    ai_service = AIService()
    return FlowService(
        session=session,
        flow_repo=flow_repo,
        entry_point_repo=entry_point_repo,
        symbol_repo=symbol_repo,
        file_repo=file_repo,
        graph_service=graph_service,
        ai_service=ai_service,
    )


# Type aliases for injected dependencies
RepoRepo = Annotated[RepoRepository, Depends(get_repo_repository)]
FileRepo = Annotated[FileRepository, Depends(get_file_repository)]
SymbolRepo = Annotated[SymbolRepository, Depends(get_symbol_repository)]
JobRepo = Annotated[JobRepository, Depends(get_job_repository)]
ParseService = Annotated[ParsingService, Depends(get_parsing_service)]
GraphSvc = Annotated[GraphService, Depends(get_graph_service)]
FlowSvc = Annotated[FlowService, Depends(get_flow_service)]

