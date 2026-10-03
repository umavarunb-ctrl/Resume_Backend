from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import (
    PaginationParams,
    get_auth_service,
    get_current_admin_user,
    get_user_repository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    UserListResponse,
    UserResponse,
    UserRoleUpdateRequest,
    UserStatusUpdateRequest,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get(
    "/users",
    response_model=UserListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all registered user accounts (Admin Only)",
    description="Returns a paginated list of all system users for administrative management.",
)
async def list_all_users(
    pagination: PaginationParams = Depends(),
    admin_user: UserResponse = Depends(get_current_admin_user),
    user_repo: UserRepository = Depends(get_user_repository),
) -> UserListResponse:
    """List paginated users for admin management."""
    user_docs, total = user_repo.list_users(skip=pagination.skip, limit=pagination.limit)
    items = [
        UserResponse(
            id=str(doc["_id"]),
            email=doc["email"],
            full_name=doc["full_name"],
            role=doc.get("role", "recruiter"),
            profile_picture=doc.get("profile_picture"),
            company_name=doc.get("company_name"),
            is_active=doc.get("is_active", True),
            created_at=doc["created_at"],
        )
        for doc in user_docs
    ]
    return UserListResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.patch(
    "/users/{user_id}/status",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update user active status (Admin Only)",
    description="Activates or deactivates a user account.",
)
async def update_user_status(
    user_id: str,
    payload: UserStatusUpdateRequest,
    admin_user: UserResponse = Depends(get_current_admin_user),
    user_repo: UserRepository = Depends(get_user_repository),
) -> UserResponse:
    """Update active status of a target user."""
    updated_doc = user_repo.update_user(user_id, {"is_active": payload.is_active})
    if updated_doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found.",
        )
    return UserResponse(
        id=str(updated_doc["_id"]),
        email=updated_doc["email"],
        full_name=updated_doc["full_name"],
        role=updated_doc.get("role", "recruiter"),
        profile_picture=updated_doc.get("profile_picture"),
        company_name=updated_doc.get("company_name"),
        is_active=updated_doc.get("is_active", True),
        created_at=updated_doc["created_at"],
    )


@router.patch(
    "/users/{user_id}/role",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update user role (Admin Only)",
    description="Promotes or demotes user role between 'admin' and 'recruiter'.",
)
async def update_user_role(
    user_id: str,
    payload: UserRoleUpdateRequest,
    admin_user: UserResponse = Depends(get_current_admin_user),
    user_repo: UserRepository = Depends(get_user_repository),
) -> UserResponse:
    """Update role of a target user."""
    new_role = payload.role.lower().strip()
    if new_role not in ("admin", "recruiter"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be either 'admin' or 'recruiter'.",
        )
    updated_doc = user_repo.update_user(user_id, {"role": new_role})
    if updated_doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found.",
        )
    return UserResponse(
        id=str(updated_doc["_id"]),
        email=updated_doc["email"],
        full_name=updated_doc["full_name"],
        role=updated_doc.get("role", "recruiter"),
        profile_picture=updated_doc.get("profile_picture"),
        company_name=updated_doc.get("company_name"),
        is_active=updated_doc.get("is_active", True),
        created_at=updated_doc["created_at"],
    )
