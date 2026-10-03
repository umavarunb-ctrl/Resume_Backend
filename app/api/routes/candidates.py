from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import (
    PaginationParams,
    get_candidate_service,
)
from app.schemas.candidate import (
    CandidateCreateRequest,
    CandidateListResponse,
    CandidateResponse,
)
from app.services.candidate_service import CandidateService

router = APIRouter(prefix="/candidates", tags=["Candidates"])


@router.post(
    "",
    response_model=CandidateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a candidate profile directly",
    description="Manually creates a candidate record without resume upload.",
)
async def create_candidate(
    payload: CandidateCreateRequest,
    candidate_service: CandidateService = Depends(get_candidate_service),
) -> CandidateResponse:
    """Create candidate profile directly."""
    return candidate_service.create_candidate(payload)


@router.get(
    "",
    response_model=CandidateListResponse,
    status_code=status.HTTP_200_OK,
    summary="List candidates with optional skills filter and search",
    description="Retrieves a paginated list of candidate profiles. Supports filtering by skills and keyword search.",
)
async def list_candidates(
    skills: Optional[List[str]] = Query(default=None, description="Filter by required skills"),
    q: Optional[str] = Query(default=None, description="Search term for name, title, or summary"),
    pagination: PaginationParams = Depends(),
    candidate_service: CandidateService = Depends(get_candidate_service),
) -> CandidateListResponse:
    """List paginated candidates."""
    return candidate_service.list_candidates(
        skills=skills,
        q=q,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/{candidate_id}",
    response_model=CandidateResponse,
    status_code=status.HTTP_200_OK,
    summary="Get candidate profile by ID",
    description="Retrieves full candidate profile details.",
)
async def get_candidate(
    candidate_id: str,
    candidate_service: CandidateService = Depends(get_candidate_service),
) -> CandidateResponse:
    """Retrieve single candidate profile."""
    return candidate_service.get_candidate(candidate_id)


@router.delete(
    "/{candidate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete candidate profile",
    description="Permanently removes a candidate profile.",
)
async def delete_candidate(
    candidate_id: str,
    candidate_service: CandidateService = Depends(get_candidate_service),
) -> None:
    """Delete candidate profile by ID."""
    candidate_service.delete_candidate(candidate_id)
