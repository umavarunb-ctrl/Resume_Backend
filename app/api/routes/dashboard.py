from fastapi import APIRouter, Depends, status
from pymongo.database import Database

from app.api.dependencies import get_database, get_current_user
from app.schemas.auth import UserResponse
from app.schemas.dashboard import DashboardStatsResponse

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get(
    "/stats",
    response_model=DashboardStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get dashboard statistics",
)
async def get_dashboard_stats(
    db: Database = Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
) -> DashboardStatsResponse:
    """Retrieve statistics for the dashboard."""
    
    total_candidates = db["candidates"].count_documents({})
    total_resumes = db["uploads"].count_documents({})
    
    # Placeholders for analytics data not currently tracked in collections
    searches_this_month = 125
    candidates_viewed = 450
    
    return DashboardStatsResponse(
        total_candidates=total_candidates,
        total_resumes=total_resumes,
        searches_this_month=searches_this_month,
        candidates_viewed=candidates_viewed,
    )
