from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class EducationModel(BaseModel):
    degree: Optional[str] = None
    college: Optional[str] = None
    date: Optional[str] = None
    place: Optional[str] = None


class CertificationModel(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    date: Optional[str] = None


class ExperienceModel(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None


class CandidateModel(BaseModel):
    """Document schema for candidate profiles stored in MongoDB."""

    id: Optional[str] = Field(default=None, alias="_id")
    upload_id: Optional[str] = Field(default=None, description="Reference to uploaded resume file")
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    title: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    experience_years: Optional[float] = None
    education: List[EducationModel] = Field(default_factory=list)
    certifications: List[CertificationModel] = Field(default_factory=list)
    experiences: List[ExperienceModel] = Field(default_factory=list)
    summary: Optional[str] = None
    embedding: Optional[List[float]] = Field(default=None, description="Dense vector embedding for vector search")
    raw_text: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "full_name": "Alice Smith",
                "email": "alice.smith@example.com",
                "phone": "+1-555-123-4567",
                "title": "Senior Backend Engineer",
                "skills": ["Python", "FastAPI", "MongoDB", "Docker"],
                "experience_years": 8.0,
                "education": ["B.S. in Computer Science"],
                "summary": "Experienced backend engineer specializing in high-throughput APIs.",
            }
        },
    )

    def to_mongo(self) -> Dict[str, Any]:
        """Convert model to MongoDB document dict, excluding None _id."""
        doc = self.model_dump(by_alias=True, exclude_none=True)
        from bson import ObjectId
        if "_id" in doc and isinstance(doc["_id"], str) and ObjectId.is_valid(doc["_id"]):
            doc["_id"] = ObjectId(doc["_id"])
        return doc
