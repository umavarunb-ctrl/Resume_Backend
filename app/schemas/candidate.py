from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class EducationResponse(BaseModel):
    degree: Optional[str] = None
    college: Optional[str] = None
    date: Optional[str] = None
    place: Optional[str] = None


class CertificationResponse(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    date: Optional[str] = None


class ExperienceResponse(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None


class CandidateResponse(BaseModel):
    """Structured candidate profile response model."""

    id: str
    upload_id: Optional[str] = None
    full_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    title: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    experience_years: Optional[float] = None
    education: List[EducationResponse] = Field(default_factory=list)
    certifications: List[CertificationResponse] = Field(default_factory=list)
    experiences: List[ExperienceResponse] = Field(default_factory=list)
    summary: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "60c72b2f9b1d8b2bad000001",
                "upload_id": "60c72b2f9b1d8b2bad000002",
                "full_name": "Alice Smith",
                "email": "alice.smith@example.com",
                "phone": "+1-555-123-4567",
                "title": "Senior Backend Engineer",
                "skills": ["Python", "FastAPI", "MongoDB", "Docker"],
                "experience_years": 8.0,
                "education": ["B.S. in Computer Science"],
                "summary": "Experienced backend engineer specializing in high-throughput APIs.",
                "created_at": "2026-09-26T00:00:00Z",
            }
        },
    )


class CandidateListResponse(BaseModel):
    """Paginated list of candidate profiles with complete pagination metadata."""

    items: List[CandidateResponse]
    total: int = Field(description="Total number of candidates matching criteria")
    page: int = Field(description="Current page number (1-indexed)")
    page_size: int = Field(description="Number of items per page")
    total_pages: int = Field(default=0, description="Total number of available pages")
    has_next: bool = Field(default=False, description="Whether a subsequent page exists")
    has_prev: bool = Field(default=False, description="Whether a preceding page exists")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [],
                "total": 45,
                "page": 1,
                "page_size": 10,
                "total_pages": 5,
                "has_next": True,
                "has_prev": False,
            }
        }
    )


class CandidateCreateRequest(BaseModel):
    """Direct candidate creation request model."""

    full_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    title: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    experience_years: Optional[float] = None
    education: List[EducationResponse] = Field(default_factory=list)
    certifications: List[CertificationResponse] = Field(default_factory=list)
    experiences: List[ExperienceResponse] = Field(default_factory=list)
    summary: Optional[str] = None
