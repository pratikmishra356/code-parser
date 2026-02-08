"""Organization management endpoints."""

from fastapi import APIRouter, HTTPException, status

from code_parser.api.dependencies import DbSession
from code_parser.api.schemas import (
    CreateOrganizationRequest,
    ErrorResponse,
    OrganizationResponse,
)
from code_parser.logging import get_logger
from code_parser.repositories.org_repository import OrgRepository

router = APIRouter(prefix="/orgs", tags=["organizations"])
logger = get_logger(__name__)


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"model": ErrorResponse, "description": "Organization already exists"},
    },
)
async def create_organization(
    request: CreateOrganizationRequest,
    session: DbSession,
) -> OrganizationResponse:
    """Create a new organization."""
    org_repo = OrgRepository(session)

    # Check for duplicate
    existing = await org_repo.get_by_name(request.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Organization already exists with name: {request.name}",
        )

    org = await org_repo.create(name=request.name, description=request.description)
    logger.info("organization_created", org_id=org.id, name=org.name)

    return OrganizationResponse(
        id=org.id,
        name=org.name,
        description=org.description,
        created_at=org.created_at,
        updated_at=org.updated_at,
    )


@router.get("", response_model=list[OrganizationResponse])
async def list_organizations(
    session: DbSession,
    limit: int = 100,
    offset: int = 0,
) -> list[OrganizationResponse]:
    """List all organizations."""
    org_repo = OrgRepository(session)
    orgs = await org_repo.list_all(limit=limit, offset=offset)
    return [
        OrganizationResponse(
            id=org.id,
            name=org.name,
            description=org.description,
            created_at=org.created_at,
            updated_at=org.updated_at,
        )
        for org in orgs
    ]


@router.get(
    "/{org_id}",
    response_model=OrganizationResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_organization(
    org_id: str,
    session: DbSession,
) -> OrganizationResponse:
    """Get organization details."""
    org_repo = OrgRepository(session)
    org = await org_repo.get_by_id(org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization not found: {org_id}",
        )

    return OrganizationResponse(
        id=org.id,
        name=org.name,
        description=org.description,
        created_at=org.created_at,
        updated_at=org.updated_at,
    )


@router.delete(
    "/{org_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
async def delete_organization(
    org_id: str,
    session: DbSession,
) -> None:
    """Delete an organization and all its repos/data."""
    org_repo = OrgRepository(session)
    deleted = await org_repo.delete(org_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization not found: {org_id}",
        )
    logger.info("organization_deleted", org_id=org_id)
