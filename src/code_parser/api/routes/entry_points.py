"""Entry point detection and retrieval endpoints."""

from fastapi import APIRouter, HTTPException, Query, status

from code_parser.api.dependencies import DbSession, FlowSvc
from code_parser.api.schemas import (
    CodeSnippetResponse,
    DetectEntryPointsRequest,
    DetectEntryPointsResponse,
    EntryPointCandidateResponse,
    EntryPointFlowResponse,
    EntryPointResponse,
    ErrorResponse,
    FlowGenerationResponse,
    FlowStepResponse,
)
from code_parser.core import EntryPointType
from code_parser.logging import get_logger
from code_parser.repositories.entry_point_repository import EntryPointRepository
from code_parser.repositories.file_repository import FileRepository
from code_parser.repositories.repo_repository import RepoRepository
from code_parser.repositories.symbol_repository import SymbolRepository
from code_parser.services.entry_point_service import EntryPointService

router = APIRouter(prefix="/repos/{repo_id}/entry-points", tags=["entry-points"])
logger = get_logger(__name__)


def _get_entry_point_service(session: DbSession) -> EntryPointService:
    """Get entry point service instance."""
    entry_point_repo = EntryPointRepository(session)
    file_repo = FileRepository(session)
    repo_repo = RepoRepository(session)
    symbol_repo = SymbolRepository(session)
    return EntryPointService(session, entry_point_repo, file_repo, repo_repo, symbol_repo)


@router.post(
    "/detect",
    response_model=DetectEntryPointsResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        404: {"model": ErrorResponse, "description": "Repository not found"},
    },
)
async def detect_entry_points(
    repo_id: str,
    request: DetectEntryPointsRequest,
    session: DbSession,
) -> DetectEntryPointsResponse:
    """
    Detect entry points for a repository.
    
    This will:
    1. Use Tree-sitter queries to find entry point candidates
    2. Use AI to confirm/reject candidates and generate names/descriptions
    3. Store confirmed entry points
    
    Returns detection statistics.
    """
    service = _get_entry_point_service(session)
    
    try:
        result = await service.detect_entry_points(
            repo_id, force_redetect=request.force_redetect
        )
        
        logger.info(
            "entry_point_detection_complete",
            repo_id=repo_id,
            candidates=result["candidates_detected"],
            confirmed=result["entry_points_confirmed"],
        )
        
        return DetectEntryPointsResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error("entry_point_detection_error", repo_id=repo_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Entry point detection failed: {str(e)}",
        ) from e


@router.get(
    "",
    response_model=list[EntryPointResponse],
    responses={404: {"model": ErrorResponse}},
)
async def list_entry_points(
    repo_id: str,
    session: DbSession,
    entry_point_type: str | None = Query(
        None,
        description="Filter by entry point type (HTTP, EVENT, SCHEDULER)",
    ),
    framework: str | None = Query(
        None,
        description="Filter by framework (e.g., flask, spring-boot)",
    ),
) -> list[EntryPointResponse]:
    """
    List confirmed entry points for a repository.
    
    Can filter by type and/or framework.
    """
    entry_point_repo = EntryPointRepository(session)
    
    # Validate entry point type if provided
    if entry_point_type:
        try:
            EntryPointType(entry_point_type.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid entry_point_type: {entry_point_type}. Must be one of: HTTP, EVENT, SCHEDULER",
            )
    
    # Get entry points
    if entry_point_type:
        entry_points = await entry_point_repo.get_by_type(
            repo_id, EntryPointType(entry_point_type.lower())
        )
    elif framework:
        entry_points = await entry_point_repo.get_by_framework(repo_id, framework)
    else:
        entry_points = await entry_point_repo.get_by_repo(repo_id)
    
    # Convert models to response format, handling metadata field
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
            "metadata": ep.entry_metadata if hasattr(ep, 'entry_metadata') else (ep.metadata if isinstance(ep.metadata, dict) else {}),
            "ai_confidence": ep.ai_confidence,
            "ai_reasoning": ep.ai_reasoning,
            "detected_at": ep.detected_at,
            "confirmed_at": ep.confirmed_at,
        }
        results.append(EntryPointResponse.model_validate(ep_dict))
    return results


@router.get(
    "/candidates",
    response_model=list[EntryPointCandidateResponse],
    responses={404: {"model": ErrorResponse}},
)
async def list_candidates(
    repo_id: str,
    session: DbSession,
) -> list[EntryPointCandidateResponse]:
    """
    List unconfirmed entry point candidates for a repository.
    
    These are candidates detected by Tree-sitter but not yet confirmed by AI.
    """
    entry_point_repo = EntryPointRepository(session)
    
    candidates = await entry_point_repo.get_candidates_by_repo(repo_id)
    
    return [EntryPointCandidateResponse.model_validate(c) for c in candidates]


@router.get(
    "/{entry_point_id}",
    response_model=EntryPointResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_entry_point(
    repo_id: str,
    entry_point_id: str,
    session: DbSession,
) -> EntryPointResponse:
    """Get details for a specific entry point."""
    entry_point_repo = EntryPointRepository(session)
    
    entry_point = await entry_point_repo.get_by_id(repo_id, entry_point_id)
    if not entry_point:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entry point not found: {entry_point_id}",
        )
    
    return EntryPointResponse.model_validate(entry_point)


@router.post(
    "/{entry_point_id}/generate-flow",
    response_model=FlowGenerationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        404: {"model": ErrorResponse, "description": "Entry point not found"},
        500: {"model": ErrorResponse, "description": "Flow generation failed"},
    },
)
async def generate_flow(
    repo_id: str,
    entry_point_id: str,
    flow_service: FlowSvc,
) -> FlowGenerationResponse:
    """
    Generate flow documentation for an entry point.
    
    This will:
    1. Analyze the entry point's downstream call graph iteratively
    2. Process 3 depth levels per iteration (max 4 iterations)
    3. Use AI to generate technical summary and flow steps
    4. Store the flow documentation in the database
    
    If a flow already exists, it will be replaced with the new one.
    """
    try:
        flow = await flow_service.generate_flow(entry_point_id, repo_id)
        
        logger.info(
            "flow_generation_complete",
            repo_id=repo_id,
            entry_point_id=entry_point_id,
            flow_name=flow.flow_name,
        )
        
        return FlowGenerationResponse(
            status="success",
            message=f"Flow documentation generated successfully: {flow.flow_name}",
            entry_point_id=entry_point_id,
            flow_id=entry_point_id,  # Using entry_point_id as flow identifier
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(
            "flow_generation_error",
            repo_id=repo_id,
            entry_point_id=entry_point_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Flow generation failed: {str(e)}",
        ) from e


@router.get(
    "/{entry_point_id}/flow",
    response_model=EntryPointFlowResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_flow(
    repo_id: str,
    entry_point_id: str,
    flow_service: FlowSvc,
    session: DbSession,
) -> EntryPointFlowResponse:
    """Get flow documentation for an entry point."""
    from code_parser.repositories.flow_repository import FlowRepository
    
    flow = await flow_service.get_flow(entry_point_id, repo_id)
    
    if not flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flow documentation not found for entry point: {entry_point_id}",
        )
    
    # Get flow model for timestamps
    flow_repo = FlowRepository(session)
    flow_model = await flow_repo.get_by_entry_point_id(entry_point_id)
    
    # Convert to response
    return EntryPointFlowResponse(
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
        created_at=flow_model.created_at if flow_model else None,
        updated_at=flow_model.updated_at if flow_model else None,
    )


