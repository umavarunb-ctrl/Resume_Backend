from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.candidate import CandidateResponse


class SearchFilter(BaseModel):
    """Filtering constraints for candidate search."""

    skills: Optional[List[str]] = Field(default=None, description="Required candidate skills")
    skill_match_mode: str = Field(default="all", description="Skill matching strategy: 'all' (must match all) or 'any' (must match at least one)")
    min_experience_years: Optional[float] = Field(default=None, ge=0, description="Minimum years of experience")
    max_experience_years: Optional[float] = Field(default=None, ge=0, description="Maximum years of experience")
    title: Optional[str] = Field(default=None, description="Target job title match")
    education: Optional[str] = Field(
        default=None,
        description="Education level filter: 'bachelor', 'master', 'phd'. Matches degree field in education array.",
    )
    location: Optional[str] = Field(
        default=None,
        description="Location filter. Matches against candidate raw_text, experience locations, or education place. Supports city names like 'Hyderabad', 'Bangalore', or 'Remote'.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "skills": ["Python", "FastAPI"],
                "skill_match_mode": "all",
                "min_experience_years": 3.0,
                "max_experience_years": 10.0,
                "title": "Backend Engineer",
                "education": "bachelor",
                "location": "Bangalore",
            }
        }
    )


class SemanticSearchRequest(BaseModel):
    """Payload for natural language semantic vector search."""

    query: str = Field(min_length=2, description="Natural language search query or job description")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of candidates to return")
    min_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum relevance score threshold (0.0 to 1.0)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "Looking for a seasoned backend engineer with distributed systems and MongoDB experience",
                "limit": 10,
                "min_score": 0.5,
            }
        }
    )


class HybridSearchRequest(BaseModel):
    """Payload for hybrid search combining semantic vector search and hard attribute filters."""

    query: str = Field(default="", description="Natural language query or job description")
    filters: Optional[SearchFilter] = Field(default=None, description="Hard filtering constraints")
    vector_weight: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Weight given to semantic vector similarity vs keyword match (0.0 to 1.0)",
    )
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of candidates to return")
    min_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum combined relevance threshold")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "Senior Python developer experienced in microservices and scalable cloud APIs",
                "filters": {
                    "skills": ["Python", "FastAPI"],
                    "min_experience_years": 4.0,
                    "max_experience_years": 15.0,
                    "title": "Backend Developer",
                    "education": "bachelor",
                    "location": "Remote",
                },
                "vector_weight": 0.7,
                "limit": 10,
                "min_score": 0.4,
            }
        }
    )


class SearchCandidateResult(BaseModel):
    """Individual candidate search match with scoring metadata."""

    candidate: CandidateResponse
    score: float = Field(description="Relevance score between 0.0 and 1.0")
    matched_skills: List[str] = Field(default_factory=list, description="Skills matching search criteria")
    match_type: str = Field(default="hybrid", description="Match type: hybrid | semantic | keyword")


class SearchResponse(BaseModel):
    """Top-level response for candidate search operations."""

    query: str
    total_matches: int
    search_type: str = "hybrid"
    results: List[SearchCandidateResult]
