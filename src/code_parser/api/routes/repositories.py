"""Repository management endpoints."""

from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from code_parser.api.dependencies import DbSession, JobRepo, RepoRepo
from code_parser.api.schemas import (
    CreateRepositoryRequest,
    ErrorResponse,
    RepositoryResponse,
)
from code_parser.logging import get_logger
from code_parser.repositories.org_repository import OrgRepository

router = APIRouter(prefix="/repos", tags=["repositories"])
logger = get_logger(__name__)

# Default org ID for backward compatibility
DEFAULT_ORG_ID = "01JKDEFAULTORG000000000000"


@router.post(
    "",
    response_model=RepositoryResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid path"},
        409: {"model": ErrorResponse, "description": "Repository already exists"},
    },
)
async def create_repository(
    request: CreateRepositoryRequest,
    session: DbSession,
    repo_repository: RepoRepo,
    job_repository: JobRepo,
) -> RepositoryResponse:
    """
    Submit a repository for parsing.
    
    The repository will be queued for background processing.
    Use GET /repos/{id} to check parsing status.
    Optionally provide org_id to assign to an organization (defaults to 'default' org).
    """
    # Validate path
    path = Path(request.path).resolve()
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path does not exist: {request.path}",
        )
    if not path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path is not a directory: {request.path}",
        )

    # Determine org_id
    org_id = request.org_id or DEFAULT_ORG_ID

    # Verify org exists
    org_repo = OrgRepository(session)
    org = await org_repo.get_by_id(org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Organization not found: {org_id}",
        )

    # Check if already exists in this org
    existing = await repo_repository.get_by_path(str(path), org_id=org_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Repository already exists with id: {existing.id}",
        )

    # Determine name
    name = request.name or path.name

    # Create repository
    repo = await repo_repository.create(name=name, root_path=str(path), org_id=org_id)

    # Create parsing job
    await job_repository.create(repo.id)

    logger.info("repository_created", repo_id=repo.id, org_id=org_id, path=str(path))

    return RepositoryResponse(
        id=repo.id,
        name=repo.name,
        org_id=repo.org_id,
        description=repo.description,
        root_path=repo.root_path,
        status=repo.status.value,
        total_files=repo.total_files,
        parsed_files=repo.parsed_files,
        progress_percentage=repo.progress_percentage,
        error_message=repo.error_message,
        languages=repo.languages,
        repo_tree=repo.repo_tree,
        created_at=repo.created_at,
        updated_at=repo.updated_at,
    )


@router.get("", response_model=list[RepositoryResponse])
async def list_repositories(
    repo_repository: RepoRepo,
    limit: int = 100,
    offset: int = 0,
) -> list[RepositoryResponse]:
    """List all repositories."""
    repos = await repo_repository.list_all(limit=limit, offset=offset)
    return [
        RepositoryResponse(
            id=repo.id,
            name=repo.name,
            org_id=repo.org_id,
            description=repo.description,
            root_path=repo.root_path,
            status=repo.status.value,
            total_files=repo.total_files,
            parsed_files=repo.parsed_files,
            progress_percentage=repo.progress_percentage,
            error_message=repo.error_message,
            languages=repo.languages,
            repo_tree=repo.repo_tree,
            created_at=repo.created_at,
            updated_at=repo.updated_at,
        )
        for repo in repos
    ]


@router.get(
    "/{repo_id}",
    response_model=RepositoryResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_repository(
    repo_id: str,
    repo_repository: RepoRepo,
) -> RepositoryResponse:
    """Get repository details and parsing status."""
    repo = await repo_repository.get_by_id(repo_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found: {repo_id}",
        )

    return RepositoryResponse(
        id=repo.id,
        name=repo.name,
        org_id=repo.org_id,
        description=repo.description,
        root_path=repo.root_path,
        status=repo.status.value,
        total_files=repo.total_files,
        parsed_files=repo.parsed_files,
        progress_percentage=repo.progress_percentage,
        error_message=repo.error_message,
        languages=repo.languages,
        repo_tree=repo.repo_tree,
        created_at=repo.created_at,
        updated_at=repo.updated_at,
    )


@router.post(
    "/{repo_id}/parse",
    status_code=status.HTTP_202_ACCEPTED,
    responses={404: {"model": ErrorResponse}},
)
async def trigger_reparse(
    repo_id: str,
    repo_repository: RepoRepo,
    job_repository: JobRepo,
) -> dict:
    """
    Trigger re-parsing of an existing repository.
    
    This will create a new parsing job and queue it for processing.
    The repository will be re-parsed with the latest parser code,
    including any new features like repo_tree and folder_structure.
    """
    repo = await repo_repository.get_by_id(repo_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found: {repo_id}",
        )
    
    # Create a new parsing job
    await job_repository.create(repo_id)
    
    logger.info("reparse_triggered", repo_id=repo_id)
    
    return {
        "message": "Re-parsing job queued",
        "repo_id": repo_id,
        "status": "pending",
    }


@router.delete(
    "/{repo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
async def delete_repository(
    repo_id: str,
    repo_repository: RepoRepo,
) -> None:
    """
    Delete a repository and all its associated data.
    
    This removes all files, symbols, and references.
    """
    deleted = await repo_repository.delete(repo_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found: {repo_id}",
        )
    logger.info("repository_deleted", repo_id=repo_id)

