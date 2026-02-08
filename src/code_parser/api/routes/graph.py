"""Call graph query endpoints."""

from fastapi import APIRouter, HTTPException, Query, status

from code_parser.api.dependencies import GraphSvc, RepoRepo
from code_parser.api.schemas import ErrorResponse, GraphNodeResponse, GraphResponse

router = APIRouter(prefix="/repos/{repo_id}", tags=["graph"])


@router.get(
    "/symbols/{symbol_id}/downstream",
    response_model=GraphResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_downstream(
    repo_id: str,
    symbol_id: str,
    repo_repository: RepoRepo,
    graph_service: GraphSvc,
    max_depth: int = Query(5, ge=1, le=10, description="Maximum traversal depth"),
) -> GraphResponse:
    """
    Get downstream call graph for a symbol.
    
    Returns all symbols that this symbol calls, directly or indirectly,
    up to the specified depth.
    
    The result shows:
    - depth: how many calls away from the root symbol
    - reference_type: the type of reference (call, import, etc.)
    """
    # Verify repo exists
    repo = await repo_repository.get_by_id(repo_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found: {repo_id}",
        )

    try:
        result = await graph_service.get_downstream(repo_id, symbol_id, max_depth)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    return GraphResponse(
        root_symbol_id=result.root_symbol_id,
        root_qualified_name=result.root_qualified_name,
        nodes=[
            GraphNodeResponse(
                id=n.id,
                name=n.name,
                qualified_name=n.qualified_name,
                kind=n.kind,
                signature=n.signature,
                depth=n.depth,
                reference_type=n.reference_type,
            )
            for n in result.nodes
        ],
        total_count=result.total_count,
    )


@router.get(
    "/symbols/{symbol_id}/upstream",
    response_model=GraphResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_upstream(
    repo_id: str,
    symbol_id: str,
    repo_repository: RepoRepo,
    graph_service: GraphSvc,
    max_depth: int = Query(5, ge=1, le=10, description="Maximum traversal depth"),
) -> GraphResponse:
    """
    Get upstream call graph for a symbol.
    
    Returns all symbols that call this symbol, directly or indirectly,
    up to the specified depth.
    
    The result shows:
    - depth: how many calls away from the root symbol
    - reference_type: the type of reference (call, import, etc.)
    """
    # Verify repo exists
    repo = await repo_repository.get_by_id(repo_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found: {repo_id}",
        )

    try:
        result = await graph_service.get_upstream(repo_id, symbol_id, max_depth)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    return GraphResponse(
        root_symbol_id=result.root_symbol_id,
        root_qualified_name=result.root_qualified_name,
        nodes=[
            GraphNodeResponse(
                id=n.id,
                name=n.name,
                qualified_name=n.qualified_name,
                kind=n.kind,
                signature=n.signature,
                depth=n.depth,
                reference_type=n.reference_type,
            )
            for n in result.nodes
        ],
        total_count=result.total_count,
    )


@router.get(
    "/symbols/{symbol_id}/context",
    responses={404: {"model": ErrorResponse}},
)
async def get_symbol_context(
    repo_id: str,
    symbol_id: str,
    repo_repository: RepoRepo,
    graph_service: GraphSvc,
    upstream_depth: int = Query(2, ge=1, le=5),
    downstream_depth: int = Query(2, ge=1, le=5),
) -> dict:
    """
    Get full context for a symbol.
    
    Returns both upstream (callers) and downstream (callees)
    for the symbol, useful for understanding how it fits
    into the larger architecture.
    """
    # Verify repo exists
    repo = await repo_repository.get_by_id(repo_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found: {repo_id}",
        )

    try:
        return await graph_service.get_symbol_context(
            repo_id, symbol_id, upstream_depth, downstream_depth
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

