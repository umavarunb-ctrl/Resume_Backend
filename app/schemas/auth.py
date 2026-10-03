from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegisterRequest(BaseModel):
    """Payload for user/recruiter registration."""

    email: EmailStr
    password: str = Field(min_length=8, description="Password with minimum 8 characters")
    full_name: str = Field(min_length=2, max_length=100)
    role: str = Field(default="recruiter", description="User role (recruiter or admin)")
    profile_picture: Optional[str] = Field(default=None, description="Profile picture URL or avatar")
    company_name: Optional[str] = Field(default=None, description="Company or organization name")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "recruiter@example.com",
                "password": "StrongPassword123!",
                "full_name": "Jane Recruiter",
                "role": "recruiter",
                "profile_picture": "https://example.com/profiles/jane.jpg",
                "company_name": "Acme Corp",
            }
        }
    )


class UserUpdateRequest(BaseModel):
    """Payload for updating user profile."""

    full_name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    profile_picture: Optional[str] = Field(default=None, description="Profile picture URL or base64 data")
    company_name: Optional[str] = Field(default=None, max_length=150, description="Company or organization name")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "full_name": "Jane Recruiter Updated",
                "profile_picture": "https://example.com/profiles/jane_new.jpg",
                "company_name": "Acme Hiring Inc",
            }
        }
    )


class UserLoginRequest(BaseModel):
    """Payload for user login with JSON."""

    email: EmailStr
    password: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "recruiter@example.com",
                "password": "StrongPassword123!",
            }
        }
    )


class TokenResponse(BaseModel):
    """JWT access token response model."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Token lifetime in seconds")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 3600,
            }
        }
    )


class TokenPayload(BaseModel):
    """Decoded JWT payload data model."""

    sub: str
    email: str
    role: str = "recruiter"
    exp: Optional[int] = None


class UserResponse(BaseModel):
    """Public user response schema without sensitive fields."""

    id: str
    email: EmailStr
    full_name: str
    role: str
    profile_picture: Optional[str] = None
    company_name: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "60c72b2f9b1d8b2bad000001",
                "email": "recruiter@example.com",
                "full_name": "Jane Recruiter",
                "role": "recruiter",
                "profile_picture": "https://example.com/profiles/jane.jpg",
                "company_name": "Acme Corp",
                "is_active": True,
                "created_at": "2026-09-26T00:00:00Z",
            }
        },
    )


class UserListResponse(BaseModel):
    """Paginated user list schema for admin management."""

    items: List[UserResponse]
    total: int
    page: int
    page_size: int


class UserStatusUpdateRequest(BaseModel):
    """Payload for updating user account active status."""

    is_active: bool = Field(description="Account active status flag")


class UserRoleUpdateRequest(BaseModel):
    """Payload for updating user role (recruiter or admin)."""

    role: str = Field(description="New user role: 'admin' or 'recruiter'")


class ForgotPasswordRequest(BaseModel):
    """Payload for requesting password reset instructions."""

    email: EmailStr

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "recruiter@example.com",
            }
        }
    )


class ForgotPasswordResponse(BaseModel):
    """Response containing reset message and token for development testing."""

    message: str
    reset_token: Optional[str] = Field(default=None, description="Signed reset token (issued for dev testing)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "If the email is registered, password reset instructions have been issued.",
                "reset_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            }
        }
    )


class ResetPasswordRequest(BaseModel):
    """Payload for executing password reset using a reset token."""

    reset_token: str = Field(description="Signed password reset token")
    new_password: str = Field(min_length=8, description="New password with minimum 8 characters")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reset_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "new_password": "NewStrongPassword123!",
            }
        }
    )


class MessageResponse(BaseModel):
    """Generic message response schema."""

    message: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Operation completed successfully.",
            }
        }
    )
