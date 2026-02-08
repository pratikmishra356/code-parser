"""Pydantic schemas for API request/response models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ============== Request Schemas ==============


class CreateOrganizationRequest(BaseModel):
    """Request to create a new organization."""

    name: str = Field(
        ...,
        description="Organization name (must be unique)",
        max_length=255,
    )
    description: str | None = Field(
        None,
        description="Optional description of the organization",
    )


class CreateRepositoryRequest(BaseModel):
    """Request to create and parse a new repository."""

    path: str = Field(
        ...,
        description="Absolute path to the codebase root directory",
        examples=["/home/user/projects/my-repo"],
    )
    name: str | None = Field(
        None,
        description="Optional name for the repository (defaults to directory name)",
        max_length=255,
    )
    org_id: str | None = Field(
        None,
        description="Organization ID (uses default org if not provided)",
    )


class GetFlowsRequest(BaseModel):
    """Request to get flows for a list of entry point IDs."""

    entry_point_ids: list[str] = Field(
        ...,
        description="List of entry point IDs to get flows for",
        min_length=1,
    )


# ============== Response Schemas ==============


class OrganizationResponse(BaseModel):
    """Organization information response."""

    id: str
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RepositoryResponse(BaseModel):
    """Repository information response."""

    id: str
    name: str
    org_id: str
    description: str | None = None
    root_path: str
    status: str
    total_files: int
    parsed_files: int
    progress_percentage: float
    error_message: str | None
    languages: list[str] | None = None
    repo_tree: dict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RepositoryBriefResponse(BaseModel):
    """Brief repository info for listing (no tree, smaller payload)."""

    id: str
    name: str
    org_id: str
    description: str | None = None
    status: str
    total_files: int
    languages: list[str] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FileDetailResponse(BaseModel):
    """File detail response including content."""

    id: str
    repo_id: str
    relative_path: str
    language: str
    content_hash: str
    content: str | None = None
    folder_structure: dict | None = None
    updated_at: datetime

    model_config = {"from_attributes": True}


class FileResponse(BaseModel):
    """File information response."""

    id: str
    relative_path: str
    language: str
    content_hash: str
    folder_structure: dict | None = None
    updated_at: datetime

    model_config = {"from_attributes": True}


class SymbolResponse(BaseModel):
    """Symbol information response."""

    id: str
    name: str
    qualified_name: str
    kind: str
    source_code: str
    signature: str | None
    file_id: str
    parent_symbol_id: str | None
    extra_data: dict

    model_config = {"from_attributes": True}


class SymbolBriefResponse(BaseModel):
    """Brief symbol info for listings."""

    id: str
    name: str
    qualified_name: str
    kind: str
    signature: str | None

    model_config = {"from_attributes": True}


class GraphNodeResponse(BaseModel):
    """A node in the call graph."""

    id: str
    name: str
    qualified_name: str | None  # Can be None for some DSL methods
    kind: str | None
    signature: str | None
    depth: int
    reference_type: str


class GraphResponse(BaseModel):
    """Call graph traversal response."""

    root_symbol_id: str
    root_qualified_name: str
    nodes: list[GraphNodeResponse]
    total_count: int


class SymbolContextResponse(BaseModel):
    """Full context for a symbol including upstream and downstream."""

    symbol: SymbolResponse
    upstream: GraphResponse
    downstream: GraphResponse


class PaginatedResponse(BaseModel):
    """Generic paginated response wrapper."""

    items: list
    total: int
    limit: int
    offset: int
    has_more: bool


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    database: str
    workers: dict


class ErrorResponse(BaseModel):
    """Error response."""

    error: str
    detail: str | None = None


# ============== Entry Point Schemas ==============


class DetectEntryPointsRequest(BaseModel):
    """Request to detect entry points for a repository."""

    force_redetect: bool = Field(
        False,
        description="If True, delete existing entry points and re-detect",
    )
    min_confidence: float = Field(
        0.7,
        description="Minimum AI confidence threshold (0-1)",
        ge=0.0,
        le=1.0,
    )


class EntryPointResponse(BaseModel):
    """Entry point information response."""

    id: str
    symbol_id: str
    file_id: str
    entry_point_type: str  # HTTP, EVENT, SCHEDULER
    framework: str
    name: str
    description: str
    metadata: dict
    ai_confidence: float
    ai_reasoning: str | None
    detected_at: datetime
    confirmed_at: datetime

    model_config = {"from_attributes": True}


class EntryPointCandidateResponse(BaseModel):
    """Entry point candidate information response."""

    id: str
    symbol_id: str
    file_id: str
    entry_point_type: str
    framework: str
    detection_pattern: str
    metadata: dict = Field(alias="entry_metadata")
    confidence_score: float | None
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class DetectEntryPointsResponse(BaseModel):
    """Response from entry point detection."""

    candidates_detected: int
    entry_points_confirmed: int
    frameworks_detected: list[str]
    statistics: dict[str, Any]


class CodeSnippetResponse(BaseModel):
    """Code snippet with context."""

    code: str
    symbol_name: str
    qualified_name: str
    file_path: str
    line_range: dict[str, int]  # {"start": int, "end": int}


class FlowStepResponse(BaseModel):
    """A single step in flow documentation."""

    step_number: int
    title: str
    description: str
    file_path: str  # Full file path containing the main code for this step
    important_log_lines: list[str]
    important_code_snippets: list[CodeSnippetResponse]


class EntryPointFlowResponse(BaseModel):
    """Complete flow documentation for an entry point."""

    entry_point_id: str
    repo_id: str
    flow_name: str
    technical_summary: str
    file_paths: list[str]  # All file paths involved in the flow
    steps: list[FlowStepResponse]
    max_depth_analyzed: int
    iterations_completed: int
    symbol_ids_analyzed: list[str]
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class FlowGenerationResponse(BaseModel):
    """Response from flow generation request."""

    status: str  # "success" or "error"
    message: str
    entry_point_id: str | None = None
    flow_id: str | None = None

