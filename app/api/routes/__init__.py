from fastapi import APIRouter

from app.api.routes.admin import router as admin_router
from app.api.routes.auth import router as auth_router
from app.api.routes.candidates import router as candidates_router
from app.api.routes.health import router as health_router
from app.api.routes.search import router as search_router
from app.api.routes.uploads import router as uploads_router
from app.api.routes.users import router as users_router
from app.api.routes.chat import router as chat_router
from app.api.routes.dashboard import router as dashboard_router

# Central API router prefixed with /api
api_router = APIRouter(prefix="/api")

# Register all active route modules
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(admin_router)
api_router.include_router(uploads_router)
api_router.include_router(candidates_router)
api_router.include_router(search_router)
api_router.include_router(chat_router)
api_router.include_router(dashboard_router)

__all__ = ["api_router"]
