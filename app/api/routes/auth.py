from typing import Optional
from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.dependencies import get_auth_service
from app.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    MessageResponse,
    ResetPasswordRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new recruiter/user account",
    description="Creates a new user profile with securely hashed password.",
)
async def register(
    payload: UserRegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    """Register user with email and password."""
    return auth_service.register(payload)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and receive JWT token",
    description="Validates user credentials and returns a signed JWT access token. Accepts JSON or OAuth2 Form Data.",
)
async def login(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Authenticate user with email and password (supports both JSON body and OAuth2 form data)."""
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        username = form.get("username") or form.get("email")
        password = form.get("password")
        if not username or not password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username/email and password are required.",
            )
        payload = UserLoginRequest(email=str(username), password=str(password))
    else:
        body = await request.json()
        payload = UserLoginRequest(**body)

    return auth_service.authenticate(payload)


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout current user session",
    description="Clears session state and invalidates client-side JWT authentication token.",
)
async def logout() -> MessageResponse:
    """Handle user logout."""
    return MessageResponse(message="Successfully logged out.")


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="Request password reset token",
    description="Generates a signed, time-limited password reset token for account recovery.",
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> ForgotPasswordResponse:
    """Request password reset for user email."""
    return auth_service.forgot_password(payload)


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset password using reset token",
    description="Validates the password reset token and sets a new password.",
)
async def reset_password(
    payload: ResetPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """Reset user password using reset token."""
    return auth_service.reset_password(payload)
