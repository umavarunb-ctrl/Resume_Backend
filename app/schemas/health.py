from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Schema for basic application health check response."""

    status: str
    service: str
    version: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "service": "Recruiter Resume Search API",
                "version": "1.0.0",
            }
        }
    )


class DatabaseHealthResponse(BaseModel):
    """Schema for database connectivity health check response."""

    status: str
    database: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "database": "connected",
            }
        }
    )
