"""
Explore API endpoints - designed for agentic AI services to discover and navigate repos.

All endpoints are scoped under /orgs/{org_id}/repos to enforce multi-tenancy.
"""

from fastapi import APIRouter, HTTPException, Query, status

from code_parser.api.dependencies import DbSession
from code_parser.api.schemas import (
    CodeSnippetResponse,
    EntryPointFlowResponse,
    EntryPointResponse,
    ErrorResponse,
    FileDetailResponse,
    FileResponse,
    FlowStepResponse,
    GetFlowsRequest,
    RepositoryBriefResponse,
)
from code_parser.logging import get_logger
from code_parser.repositories.entry_point_repository import EntryPointRepository
from code_parser.repositories.file_repository import FileRepository
from code_parser.repositories.flow_repository import FlowRepository
from code_parser.repositories.org_repository import OrgRepository
from code_parser.repositories.repo_repository import RepoRepository

router = APIRouter(prefix="/orgs/{org_id}/repos", tags=["explore"])
logger = get_logger(__name__)


async def _verify_org(session: DbSession, org_id: str) -> None:
    """Verify organization exists."""
    org_repo = OrgRepository(session)
    org = await org_repo.get_by_id(org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization not found: {org_id}",
        )


async def _verify_repo(session: DbSession, org_id: str, repo_id: str) -> None:
    """Verify repo exists within organization."""
    repo_repo = RepoRepository(session)
    repo = await repo_repo.get_by_id_and_org(repo_id, org_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found: {repo_id} in org {org_id}",
        )


# ============================================================
# 1. List repos for an org (with regex search on name/description)
# ============================================================

@router.get(
    "",
    response_model=list[RepositoryBriefResponse],
    responses={404: {"model": ErrorResponse}},
)
async def list_repos_for_org(
    org_id: str,
    session: DbSession,
    search: str | None = Query(
        None,
        description="Regex pattern to match against repo name or description",
    ),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[RepositoryBriefResponse]:
    """
    List all repositories for an organization.

    Returns repo name, description, status, and languages.
    Supports regex search on name and description fields.

    **Example search patterns:**
    - `payment` - matches repos with 'payment' in name or description (case-insensitive)
    - `^api-` - matches repos whose name starts with 'api-'
    - `(kafka|rabbitmq)` - matches repos mentioning kafka or rabbitmq
    """
    await _verify_org(session, org_id)

    repo_repo = RepoRepository(session)
    repos = await repo_repo.list_by_org(org_id, search=search, limit=limit, offset=offset)

    return [
        RepositoryBriefResponse(
            id=repo.id,
            name=repo.name,
            org_id=repo.org_id,
            description=repo.description,
            status=repo.status.value,
            total_files=repo.total_files,
            languages=repo.languages,
            created_at=repo.created_at,
            updated_at=repo.updated_at,
        )
        for repo in repos
    ]


# ============================================================
# 2. List entry points for a repo (with regex search)
# ============================================================

@router.get(
    "/{repo_id}/entry-points",
    response_model=list[EntryPointResponse],
    responses={404: {"model": ErrorResponse}},
)
async def list_entry_points_for_repo(
    org_id: str,
    repo_id: str,
    session: DbSession,
    search: str | None = Query(
        None,
        description="Regex pattern to match against entry point name or description",
    ),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[EntryPointResponse]:
    """
    List all confirmed entry points for a repository.

    Supports regex search on name and description fields.

    **Example search patterns:**
    - `payment` - matches entry points about payments
    - `GET|POST` - matches entry points with GET or POST in description
    - `kafka.*consumer` - matches kafka consumer entry points
    """
    await _verify_org(session, org_id)
    await _verify_repo(session, org_id, repo_id)

    entry_point_repo = EntryPointRepository(session)
    entry_points = await entry_point_repo.list_by_repo_with_search(
        repo_id, search=search, limit=limit, offset=offset
    )

    results = []
    for ep in entry_points:
        ep_dict = {
            "id": ep.id,
            "symbol_id": ep.symbol_id,
            "file_id": ep.file_id,
            "entry_point_type": ep.entry_point_type,
            "framework": ep.framework,
            "name": ep.name,
            "description": ep.description,
            "metadata": ep.entry_metadata if hasattr(ep, 'entry_metadata') else {},
            "ai_confidence": ep.ai_confidence,
            "ai_reasoning": ep.ai_reasoning,
            "detected_at": ep.detected_at,
            "confirmed_at": ep.confirmed_at,
        }
        results.append(EntryPointResponse.model_validate(ep_dict))
    return results


# ============================================================
# 3. Get flows for a list of entry point IDs
# ============================================================

@router.post(
    "/{repo_id}/flows",
    response_model=list[EntryPointFlowResponse],
    responses={404: {"model": ErrorResponse}},
)
async def get_flows_for_entry_points(
    org_id: str,
    repo_id: str,
    request: GetFlowsRequest,
    session: DbSession,
) -> list[EntryPointFlowResponse]:
    """
    Get flow documentation for a list of entry point IDs.

    Provide a list of entry_point_ids and get their flow details back.
    Entry points without generated flows will be silently skipped.
    """
    await _verify_org(session, org_id)
    await _verify_repo(session, org_id, repo_id)

    # Verify entry points belong to this repo
    entry_point_repo = EntryPointRepository(session)
    entry_points = await entry_point_repo.get_by_ids(repo_id, request.entry_point_ids)
    valid_ep_ids = {ep.id for ep in entry_points}

    flow_repo = FlowRepository(session)
    results = []

    for ep_id in request.entry_point_ids:
        if ep_id not in valid_ep_ids:
            continue

        flow_model = await flow_repo.get_by_entry_point_id(ep_id)
        if not flow_model:
            continue

        flow = flow_repo.model_to_core(flow_model)

        results.append(
            EntryPointFlowResponse(
                entry_point_id=flow.entry_point_id,
                repo_id=flow.repo_id,
                flow_name=flow.flow_name,
                technical_summary=flow.technical_summary,
                file_paths=flow.file_paths,
                steps=[
                    FlowStepResponse(
                        step_number=step.step_number,
                        title=step.title,
                        description=step.description,
                        file_path=step.file_path,
                        important_log_lines=step.important_log_lines,
                        important_code_snippets=[
                            CodeSnippetResponse(
                                code=snippet.code,
                                symbol_name=snippet.symbol_name,
                                qualified_name=snippet.qualified_name,
                                file_path=snippet.file_path,
                                line_range=snippet.line_range,
                            )
                            for snippet in step.important_code_snippets
                        ],
                    )
                    for step in flow.steps
                ],
                max_depth_analyzed=flow.max_depth_analyzed,
                iterations_completed=flow.iterations_completed,
                symbol_ids_analyzed=flow.symbol_ids_analyzed,
                created_at=flow_model.created_at,
                updated_at=flow_model.updated_at,
            )
        )

    return results


# ============================================================
# 4. List files for a repo (with regex search)
# ============================================================

@router.get(
    "/{repo_id}/files",
    response_model=list[FileResponse],
    responses={404: {"model": ErrorResponse}},
)
async def list_files_for_repo(
    org_id: str,
    repo_id: str,
    session: DbSession,
    search: str | None = Query(
        None,
        description="Regex pattern to match against file relative path",
    ),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[FileResponse]:
    """
    List all parsed files for a repository.

    Supports regex search on the file's relative path.

    **Example search patterns:**
    - `\\.py$` - all Python files
    - `controller|handler` - files with controller or handler in path
    - `src/main/.*Service` - Java/Kotlin service files in src/main
    """
    await _verify_org(session, org_id)
    await _verify_repo(session, org_id, repo_id)

    file_repo = FileRepository(session)
    files = await file_repo.list_by_repo_with_search(
        repo_id, search=search, limit=limit, offset=offset
    )

    return [
        FileResponse(
            id=f.id,
            relative_path=f.relative_path,
            language=f.language,
            content_hash=f.content_hash,
            folder_structure=f.folder_structure,
            updated_at=f.updated_at,
        )
        for f in files
    ]


# ============================================================
# 5. Get file detail by file_id, repo_id, org_id
# ============================================================

@router.get(
    "/{repo_id}/files/{file_id}",
    response_model=FileDetailResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_file_detail(
    org_id: str,
    repo_id: str,
    file_id: str,
    session: DbSession,
) -> FileDetailResponse:
    """
    Get full detail for a specific file including its content.

    Returns file metadata, content, and folder structure.
    """
    await _verify_org(session, org_id)
    await _verify_repo(session, org_id, repo_id)

    file_repo = FileRepository(session)
    file = await file_repo.get_by_id(file_id)

    if not file or file.repo_id != repo_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {file_id} in repo {repo_id}",
        )

    return FileDetailResponse(
        id=file.id,
        repo_id=file.repo_id,
        relative_path=file.relative_path,
        language=file.language,
        content_hash=file.content_hash,
        content=file.content,
        folder_structure=file.folder_structure,
        updated_at=file.updated_at,
    )
