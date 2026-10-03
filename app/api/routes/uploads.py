from typing import List

from fastapi import APIRouter, Depends, File, UploadFile, status

from app.api.dependencies import (
    PaginationParams,
    get_resume_service,
    get_candidate_service,
)
from app.schemas.upload import (
    UploadDetailResponse,
    UploadListResponse,
    UploadResponse,
)
from app.schemas.candidate import CandidateResponse
from app.services.resume_service import ResumeService
from app.services.candidate_service import CandidateService

router = APIRouter(prefix="/uploads", tags=["Uploads"])


@router.post(
    "/resume",
    response_model=CandidateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload resume PDF and parse into candidate profile",
    description="Validates the PDF resume, extracts text, stores upload metadata, and automatically parses it into a candidate profile.",
)
async def upload_resume(
    file: UploadFile = File(..., description="PDF resume file (max 10MB)"),
    resume_service: ResumeService = Depends(get_resume_service),
    candidate_service: CandidateService = Depends(get_candidate_service),
) -> CandidateResponse:
    """Handle resume PDF upload, extract text, and parse into a candidate profile."""
    upload_res = await resume_service.process_resume_upload(file, current_user_id="test_user")
    return candidate_service.parse_and_create_from_upload(upload_res.file_id)


@router.post(
    "/batch",
    response_model=List[CandidateResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Upload multiple resume PDFs and parse them into candidate profiles",
    description="Validates multiple PDF resumes, extracts text, stores upload metadata, and automatically parses them into candidate profiles.",
)
async def upload_multiple_resumes(
    files: List[UploadFile] = File(..., description="List of PDF resume files (max 10MB each)"),
    resume_service: ResumeService = Depends(get_resume_service),
    candidate_service: CandidateService = Depends(get_candidate_service),
) -> List[CandidateResponse]:
    """Handle multiple resume PDF uploads, extract text, and parse into candidate profiles."""
    responses = []
    for file in files:
        upload_res = await resume_service.process_resume_upload(file, current_user_id="test_user")
        candidate = candidate_service.parse_and_create_from_upload(upload_res.file_id)
        responses.append(candidate)
    return responses

@router.get(
    "/{file_id}",
    response_model=UploadDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get upload record and full extracted text",
    description="Retrieves the metadata and complete extracted text for a specific resume upload (auth disabled for testing).",
)
async def get_upload_detail(
    file_id: str,
    resume_service: ResumeService = Depends(get_resume_service),
) -> UploadDetailResponse:
    """Retrieve resume upload details without requiring auth bearer."""
    return resume_service.get_upload_detail(file_id, current_user_id=None)


@router.get(
    "",
    response_model=UploadListResponse,
    status_code=status.HTTP_200_OK,
    summary="List uploaded resumes",
    description="Returns a paginated list of uploaded resumes (auth disabled for testing).",
)
async def list_uploads(
    pagination: PaginationParams = Depends(),
    resume_service: ResumeService = Depends(get_resume_service),
) -> UploadListResponse:
    """List paginated uploads without requiring auth bearer."""
    return resume_service.list_user_uploads(
        user_id=None,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/{file_id}/download",
    status_code=status.HTTP_200_OK,
    summary="Get a secure, short-lived download URL for the resume PDF",
    description="Returns a Pre-Authenticated Request (PAR) URL for the original uploaded PDF from Oracle Object Storage.",
)
async def get_resume_download_url(
    file_id: str,
    resume_service: ResumeService = Depends(get_resume_service),
) -> dict:
    """Get a secure download URL for the resume PDF."""
    url = resume_service.get_resume_download_url(file_id, current_user_id=None)
    return {"url": url}


@router.delete(
    "/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a resume upload",
    description="Deletes the resume upload metadata and the original PDF from Oracle Object Storage.",
)
async def delete_resume(
    file_id: str,
    resume_service: ResumeService = Depends(get_resume_service),
) -> None:
    """Delete a resume upload."""
    resume_service.delete_resume(file_id, current_user_id=None)
