from pydantic import BaseModel, Field

class DashboardStatsResponse(BaseModel):
    total_candidates: int = Field(description="Total number of candidates in the system")
    total_resumes: int = Field(description="Total number of resumes uploaded")
    searches_this_month: int = Field(default=0, description="Number of searches performed this month (placeholder)")
    candidates_viewed: int = Field(default=0, description="Number of candidate profiles viewed (placeholder)")
