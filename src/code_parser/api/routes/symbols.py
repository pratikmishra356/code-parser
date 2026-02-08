"""Symbol query endpoints."""

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from code_parser.api.dependencies import FileRepo, RepoRepo, SymbolRepo
from code_parser.api.schemas import (
    ErrorResponse,
    FileResponse,
    SymbolBriefResponse,
    SymbolResponse,
)
from code_parser.core import SymbolKind

router = APIRouter(prefix="/repos/{repo_id}", tags=["symbols"])


# Request/Response models for symbol details endpoint
class SymbolDetailsRequest(BaseModel):
    """Request for getting symbol details by path and name."""
    path_name: str = Field(
        ...,
        description="Package/class path (e.g., 'com.toasttab.service.MyService')",
        examples=["com.toasttab.service.ccfraud.resources.RiskAssessmentResource"],
    )
    symbol_name: str = Field(
        ...,
        description="Symbol name (method, class, function, etc.)",
        examples=["riskAssessment", "bulkCreateFromCsv"],
    )
    depth: int = Field(
        default=0,
        ge=0,
        le=10,
        description="Context depth: 0 = symbol only, 1+ = include upstream/downstream",
    )


class SymbolDetailItem(BaseModel):
    """Symbol detail in response."""
    id: str | None = None
    name: str
    qualified_name: str | None = None  # For internal symbols
    kind: str | None = None
    source_code: str | None = None
    signature: str | None = None
    relative_path: str | None = None
    language: str | None = None
    reference_type: str | None = None
    # For traversal via get_symbol_details(path_name, symbol_name)
    target_file_path: str | None = None  # The file/class path (dot notation)
    target_symbol_name: str | None = None  # The symbol name
    depth: int | None = None
    is_external: bool = False  # True if symbol is not in the repo (e.g., JDK classes)


class SymbolWithContext(BaseModel):
    """Single symbol with its context."""
    symbol: SymbolDetailItem
    upstream: list[SymbolDetailItem] = []
    downstream: list[SymbolDetailItem] = []


class SymbolDetailsResponse(BaseModel):
    """Response for symbol details - may contain multiple matches."""
    matches: list[SymbolWithContext]
    total_matches: int


class SymbolStats(BaseModel):
    """Symbol statistics for a repository."""
    total: int
    by_kind: dict[str, int]
    by_language: dict[str, int]


@router.get(
    "/stats",
    response_model=SymbolStats,
    responses={404: {"model": ErrorResponse}},
)
async def get_symbol_stats(
    repo_id: str,
    repo_repository: RepoRepo,
    symbol_repository: SymbolRepo,
) -> SymbolStats:
    """Get symbol statistics for a repository."""
    repo = await repo_repository.get_by_id(repo_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found: {repo_id}",
        )

    stats = await symbol_repository.get_stats(repo_id)
    return SymbolStats(**stats)


@router.get(
    "/files",
    response_model=list[FileResponse],
    responses={404: {"model": ErrorResponse}},
)
async def list_files(
    repo_id: str,
    repo_repository: RepoRepo,
    file_repository: FileRepo,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[FileResponse]:
    """List all parsed files in a repository."""
    # Verify repo exists
    repo = await repo_repository.get_by_id(repo_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found: {repo_id}",
        )

    files = await file_repository.list_by_repo(repo_id, limit=limit, offset=offset)

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


@router.get(
    "/symbols",
    response_model=list[SymbolBriefResponse],
    responses={404: {"model": ErrorResponse}},
)
async def list_symbols(
    repo_id: str,
    repo_repository: RepoRepo,
    symbol_repository: SymbolRepo,
    kind: SymbolKind | None = Query(None, description="Filter by symbol kind"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[SymbolBriefResponse]:
    """
    List symbols in a repository.
    
    Can be filtered by symbol kind (function, class, method, etc.).
    """
    # Verify repo exists
    repo = await repo_repository.get_by_id(repo_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found: {repo_id}",
        )

    symbols = await symbol_repository.list_symbols(
        repo_id, kind=kind, limit=limit, offset=offset
    )

    return [
        SymbolBriefResponse(
            id=s.id,
            name=s.name,
            qualified_name=s.qualified_name,
            kind=s.kind,
            signature=s.signature,
        )
        for s in symbols
    ]


@router.get(
    "/symbols/search",
    response_model=list[SymbolBriefResponse],
    responses={404: {"model": ErrorResponse}},
)
async def search_symbols(
    repo_id: str,
    q: str,
    repo_repository: RepoRepo,
    symbol_repository: SymbolRepo,
    limit: int = Query(50, ge=1, le=200),
) -> list[SymbolBriefResponse]:
    """
    Search symbols by name prefix.
    
    Returns symbols whose names start with the query string.
    """
    # Verify repo exists
    repo = await repo_repository.get_by_id(repo_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found: {repo_id}",
        )

    if len(q) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query must be at least 2 characters",
        )

    symbols = await symbol_repository.search_symbols(repo_id, q, limit=limit)

    return [
        SymbolBriefResponse(
            id=s.id,
            name=s.name,
            qualified_name=s.qualified_name,
            kind=s.kind,
            signature=s.signature,
        )
        for s in symbols
    ]


@router.get(
    "/symbols/{symbol_id}",
    response_model=SymbolResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_symbol(
    repo_id: str,
    symbol_id: str,
    repo_repository: RepoRepo,
    symbol_repository: SymbolRepo,
) -> SymbolResponse:
    """Get detailed information about a specific symbol."""
    # Verify repo exists
    repo = await repo_repository.get_by_id(repo_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found: {repo_id}",
        )

    symbol = await symbol_repository.get_symbol_by_id(symbol_id)
    if not symbol or symbol.repo_id != repo_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol not found: {symbol_id}",
        )

    return SymbolResponse(
        id=symbol.id,
        name=symbol.name,
        qualified_name=symbol.qualified_name,
        kind=symbol.kind,
        source_code=symbol.source_code,
        signature=symbol.signature,
        file_id=symbol.file_id,
        parent_symbol_id=symbol.parent_symbol_id,
        extra_data=symbol.extra_data or {},
    )


@router.get(
    "/files/{file_id}/symbols",
    response_model=list[SymbolBriefResponse],
    responses={404: {"model": ErrorResponse}},
)
async def get_symbols_in_file(
    repo_id: str,
    file_id: str,
    repo_repository: RepoRepo,
    file_repository: FileRepo,
    symbol_repository: SymbolRepo,
) -> list[SymbolBriefResponse]:
    """Get all symbols defined in a specific file."""
    # Verify repo exists
    repo = await repo_repository.get_by_id(repo_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found: {repo_id}",
        )

    # Verify file exists and belongs to repo
    file = await file_repository.get_by_id(file_id)
    if not file or file.repo_id != repo_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {file_id}",
        )

    symbols = await symbol_repository.get_symbols_in_file(file_id)

    return [
        SymbolBriefResponse(
            id=s.id,
            name=s.name,
            qualified_name=s.qualified_name,
            kind=s.kind,
            signature=s.signature,
        )
        for s in symbols
    ]


@router.post(
    "/symbols/details",
    response_model=SymbolDetailsResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_symbol_details(
    repo_id: str,
    request: SymbolDetailsRequest,
    repo_repository: RepoRepo,
    symbol_repository: SymbolRepo,
) -> SymbolDetailsResponse:
    """
    Get symbol details by path and name with optional context.
    
    This endpoint is designed for AI agents and exception/stacktrace resolution.
    Given a package path (e.g., 'com.toasttab.service.MyService') and
    symbol name (e.g., 'myMethod'), returns the symbol's source code
    and optionally upstream/downstream dependencies.
    
    **Returns multiple matches** if the same path exists in different modules.
    
    **Example use case - Exception resolution:**
    
    From a stack trace like:
    ```
    com.toasttab.service.ccfraud.resources.RiskAssessmentResource.riskAssessment at line 48
    ```
    
    You can call:
    ```json
    {
        "path_name": "com.toasttab.service.ccfraud.resources.RiskAssessmentResource",
        "symbol_name": "riskAssessment",
        "depth": 1
    }
    ```
    
    This returns the method's source code plus what calls it (upstream)
    and what it calls (downstream).
    """
    # Verify repo exists
    repo = await repo_repository.get_by_id(repo_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found: {repo_id}",
        )

    # Get all matching symbols with context
    results = await symbol_repository.get_symbol_details_with_context(
        repo_id=repo_id,
        path_pattern=request.path_name,
        symbol_name=request.symbol_name,
        depth=request.depth,
    )

    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol not found: {request.symbol_name} in path matching {request.path_name}",
        )

    # Build response with all matches
    matches = []
    for result in results:
        symbol_data = result["symbol"]
        
        match = SymbolWithContext(
            symbol=SymbolDetailItem(
                id=symbol_data["id"],
                name=symbol_data["name"],
                qualified_name=symbol_data["qualified_name"],
                kind=symbol_data["kind"],
                source_code=symbol_data["source_code"],
                signature=symbol_data["signature"],
                relative_path=symbol_data["relative_path"],
                language=symbol_data["language"],
            ),
            upstream=[
                SymbolDetailItem(
                    id=u["id"],
                    name=u["name"],
                    qualified_name=u["qualified_name"],
                    kind=u["kind"],
                    source_code=u["source_code"],
                    signature=u["signature"],
                    reference_type=u["reference_type"],
                    depth=u["depth"],
                )
                for u in result["upstream"]
            ],
            downstream=[
                SymbolDetailItem(
                    id=d["id"],
                    name=d["name"] if d["name"] else d["target_symbol_name"],
                    qualified_name=d["qualified_name"],
                    kind=d["kind"],
                    source_code=d["source_code"],
                    signature=d["signature"],
                    reference_type=d["reference_type"],
                    target_file_path=d.get("target_file_path"),
                    target_symbol_name=d.get("target_symbol_name"),
                    depth=d["depth"],
                    is_external=d["id"] is None,
                )
                for d in result["downstream"]
            ],
        )
        matches.append(match)
    
    return SymbolDetailsResponse(
        matches=matches,
        total_matches=len(matches),
    )

