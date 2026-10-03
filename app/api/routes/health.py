from fastapi import APIRouter, Response, status
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import db_manager
from app.schemas.health import DatabaseHealthResponse, HealthResponse

router = APIRouter(prefix="/health", tags=["Health"])


@router.get(
    "",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Application Health Check",
    description="Returns the operational status of the API service.",
)
async def health_check() -> HealthResponse:
    """Check API operational health status."""
    return HealthResponse(
        status="healthy",
        service=settings.APP_NAME,
        version=settings.APP_VERSION,
    )


@router.get(
    "/database",
    response_model=DatabaseHealthResponse,
    responses={
        200: {"model": DatabaseHealthResponse, "description": "Database is connected and healthy"},
        503: {"model": DatabaseHealthResponse, "description": "Database is disconnected or unreachable"},
    },
    summary="Database Health Check",
    description="Tests connectivity to the configured MongoDB database.",
)
async def database_health_check() -> Response:
    """Test connectivity to MongoDB Atlas."""
    is_healthy, _ = db_manager.ping()

    if is_healthy:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "healthy", "database": "connected"},
        )

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "unhealthy", "database": "disconnected"},
    )
