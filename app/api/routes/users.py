from fastapi import APIRouter, Depends, status, UploadFile, File

from app.api.dependencies import get_auth_service, get_current_user
from app.schemas.auth import UserResponse, UserUpdateRequest
from app.services.auth_service import AuthService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
    description="Returns full profile details (full name, email, profile picture, company name, role) for the authenticated user.",
)
async def get_current_user_profile(
    current_user: UserResponse = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    """Retrieve authenticated user's profile details."""
    if current_user.profile_picture and current_user.profile_picture.startswith("oci:"):
        current_user.profile_picture = auth_service.get_profile_picture_url(current_user.id)
    return current_user


@router.put(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update current user profile",
    description="Updates authenticated user details including full name, profile picture URL/base64, and company name.",
)
async def update_user_profile(
    payload: UserUpdateRequest,
    current_user: UserResponse = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    """Update authenticated user's profile details."""
    updated_user = auth_service.update_profile(current_user.id, payload)
    if updated_user.profile_picture and updated_user.profile_picture.startswith("oci:"):
        updated_user.profile_picture = auth_service.get_profile_picture_url(updated_user.id)
    return updated_user


@router.post(
    "/me/profile-picture",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload profile picture",
    description="Uploads a new profile picture to Object Storage and updates the user profile."
)
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: UserResponse = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    """Upload a new profile picture."""
    updated_user = await auth_service.upload_profile_picture(current_user.id, file)
    if updated_user.profile_picture and updated_user.profile_picture.startswith("oci:"):
        updated_user.profile_picture = auth_service.get_profile_picture_url(updated_user.id)
    return updated_user


@router.delete(
    "/me/profile-picture",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete profile picture",
    description="Deletes the user's profile picture from Object Storage and the database."
)
async def delete_profile_picture(
    current_user: UserResponse = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    """Delete the profile picture."""
    return auth_service.delete_profile_picture(current_user.id)
