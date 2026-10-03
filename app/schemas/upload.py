from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class UploadResponse(BaseModel):
    """Summary response for an uploaded resume."""

    file_id: str
    filename: str
    file_size: int = Field(description="File size in bytes")
    page_count: int
    char_count: int
    status: str
    text_preview: str = Field(description="First 300 characters of extracted resume text")
    created_at: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file_id": "60c72b2f9b1d8b2bad000001",
                "filename": "candidate_resume.pdf",
                "file_size": 204800,
                "page_count": 2,
                "char_count": 4250,
                "status": "extracted",
                "text_preview": "John Doe - Senior Software Engineer with 7+ years of experience...",
                "created_at": "2026-09-26T00:00:00Z",
            }
        }
    )


class UploadDetailResponse(BaseModel):
    """Detailed response including full extracted resume text."""

    file_id: str
    filename: str
    file_size: int
    page_count: int
    char_count: int
    status: str
    raw_text: str
    created_at: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file_id": "60c72b2f9b1d8b2bad000001",
                "filename": "candidate_resume.pdf",
                "file_size": 204800,
                "page_count": 2,
                "char_count": 4250,
                "status": "extracted",
                "raw_text": "Full extracted resume text goes here...",
                "created_at": "2026-09-26T00:00:00Z",
            }
        }
    )


class UploadListResponse(BaseModel):
    """Paginated list of resume uploads."""

    items: List[UploadResponse]
    total: int
    page: int
    page_size: int
