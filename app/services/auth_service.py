import uuid
from fastapi import HTTPException, status, UploadFile

from app.core.config import settings
from app.services.storage_service import StorageService
from app.core.security import (
    create_access_token,
    create_reset_token,
    decode_reset_token,
    hash_password,
    verify_password,
)
from app.models.user import UserModel
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    MessageResponse,
    ResetPasswordRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
    UserUpdateRequest,
)


class AuthService:
    """Service orchestrating user registration, authentication, profile updates, password resets, and JWT issuance."""

    def __init__(self, user_repo: UserRepository, storage_service: StorageService) -> None:
        self.user_repo = user_repo
        self.storage_service = storage_service

    def register(self, req: UserRegisterRequest) -> UserResponse:
        """Register a new user account."""
        existing_user = self.user_repo.find_by_email(req.email)
        if existing_user is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email address already exists.",
            )

        hashed = hash_password(req.password)
        new_user = UserModel(
            email=req.email,
            full_name=req.full_name,
            hashed_password=hashed,
            role=req.role,
            profile_picture=req.profile_picture,
            company_name=req.company_name,
            is_active=True,
        )

        created_doc = self.user_repo.create(new_user)
        return UserResponse(
            id=str(created_doc["_id"]),
            email=created_doc["email"],
            full_name=created_doc["full_name"],
            role=created_doc.get("role", "recruiter"),
            profile_picture=created_doc.get("profile_picture"),
            company_name=created_doc.get("company_name"),
            is_active=created_doc.get("is_active", True),
            created_at=created_doc["created_at"],
        )

    def authenticate(self, req: UserLoginRequest) -> TokenResponse:
        """Authenticate user credentials and return an access token."""
        user = self.user_repo.find_by_email(req.email)
        if user is None or not verify_password(req.password, user.get("hashed_password", "")):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive.",
            )

        token_payload = {
            "sub": str(user["_id"]),
            "email": user["email"],
            "role": user.get("role", "recruiter"),
        }
        token = create_access_token(token_payload)

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=settings.JWT_EXPIRE_MINUTES * 60,
        )

    def update_profile(self, user_id: str, req: UserUpdateRequest) -> UserResponse:
        """Update authenticated user profile attributes."""
        update_data = req.model_dump(exclude_unset=True)
        if not update_data:
            user_doc = self.user_repo.find_by_id(user_id)
            if user_doc is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User account not found.",
                )
        else:
            user_doc = self.user_repo.update_user(user_id, update_data)
            if user_doc is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User account not found.",
                )

        return UserResponse(
            id=str(user_doc["_id"]),
            email=user_doc["email"],
            full_name=user_doc["full_name"],
            role=user_doc.get("role", "recruiter"),
            profile_picture=user_doc.get("profile_picture"),
            company_name=user_doc.get("company_name"),
            is_active=user_doc.get("is_active", True),
            created_at=user_doc["created_at"],
        )

    def forgot_password(self, req: ForgotPasswordRequest) -> ForgotPasswordResponse:
        """Generate a password reset token for the specified user email."""
        user = self.user_repo.find_by_email(req.email)
        if user is None:
            # Maintain security response consistency
            return ForgotPasswordResponse(
                message="If the email address is registered, password reset instructions have been issued.",
                reset_token=None,
            )

        reset_token = create_reset_token(user["email"])
        return ForgotPasswordResponse(
            message="Password reset token issued successfully.",
            reset_token=reset_token,
        )

    def reset_password(self, req: ResetPasswordRequest) -> MessageResponse:
        """Verify password reset token and update user password."""
        email = decode_reset_token(req.reset_token)
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired password reset token.",
            )

        user = self.user_repo.find_by_email(email)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User account no longer exists.",
            )

        new_hashed = hash_password(req.new_password)
        self.user_repo.update_user(str(user["_id"]), {"hashed_password": new_hashed})
        return MessageResponse(message="Password has been successfully reset.")

    async def upload_profile_picture(self, user_id: str, file: UploadFile) -> UserResponse:
        """Upload a profile picture to Object Storage and update user."""
        user_doc = self.user_repo.find_by_id(user_id)
        if not user_doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
            
        allowed_types = {"image/jpeg", "image/png", "image/webp"}
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only JPEG, PNG, and WebP images are allowed.")
            
        file_bytes = await file.read()
        max_bytes = 5 * 1024 * 1024  # 5 MB
        if len(file_bytes) > max_bytes:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large. Max 5MB.")
            
        if self.storage_service.enabled:
            # Delete old profile picture if it was in OCI
            old_pic = user_doc.get("profile_picture")
            if old_pic and old_pic.startswith("oci:"):
                old_object_name = old_pic[4:]
                try:
                    self.storage_service.delete_file(old_object_name)
                except Exception:
                    pass
            
            ext = file.filename.split(".")[-1] if file.filename and "." in file.filename else "jpg"
            object_name = f"profile_pictures/{user_id}/{uuid.uuid4().hex}.{ext}"
            
            self.storage_service.upload_file(file_bytes, object_name, content_type=file.content_type)
            
            # Update user profile with oci prefix
            return self.update_profile(user_id, UserUpdateRequest(profile_picture=f"oci:{object_name}"))
        else:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Storage service is not enabled.")
            
    def get_profile_picture_url(self, user_id: str) -> str:
        """Generate a short-lived URL for the user's profile picture if stored in OCI."""
        user_doc = self.user_repo.find_by_id(user_id)
        if not user_doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
            
        pic = user_doc.get("profile_picture")
        if not pic:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User has no profile picture.")
            
        if pic.startswith("oci:"):
            object_name = pic[4:]
            if self.storage_service.enabled:
                return self.storage_service.generate_presigned_url(object_name, expires_in_minutes=60)
            else:
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Storage service is not enabled.")
        else:
            # It's already a standard URL or base64
            return pic

    def delete_profile_picture(self, user_id: str) -> UserResponse:
        """Delete the user's profile picture from Object Storage and MongoDB."""
        user_doc = self.user_repo.find_by_id(user_id)
        if not user_doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
            
        pic = user_doc.get("profile_picture")
        if not pic:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User does not have a profile picture.")
            
        if pic.startswith("oci:"):
            object_name = pic[4:]
            if self.storage_service.enabled:
                try:
                    self.storage_service.delete_file(object_name)
                except Exception as e:
                    pass # If it's already deleted or fails, we still want to clear it from the DB
            else:
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Storage service is not enabled.")
        
        # Update user profile to remove the picture
        return self.update_profile(user_id, UserUpdateRequest(profile_picture=None))
