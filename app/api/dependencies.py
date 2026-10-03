from functools import lru_cache
from typing import Optional
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from pymongo.database import Database

from app.core.config import Settings, get_settings
from app.core.database import db_manager
from app.core.security import decode_access_token
from app.repositories.candidate_repository import CandidateRepository
from app.repositories.upload_repository import UploadRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserResponse
from app.services.auth_service import AuthService
from app.services.candidate_service import CandidateService
from app.services.embedding_service import EmbeddingService
from app.services.parsing_service import ParsingService
from app.services.pdf_service import PDFService
from app.services.resume_service import ResumeService
from app.services.search_service import SearchService
from app.services.storage_service import StorageService

# Chat repositories
from app.repositories.chat.conversation_repository import ConversationRepository
from app.repositories.chat.message_repository import MessageRepository
from app.repositories.chat.notification_repository import NotificationRepository

# Chat services
from app.services.chat.authorization_service import AuthorizationService
from app.services.chat.conversation_service import ConversationService
from app.services.chat.message_service import MessageService
from app.services.chat.notification_service import NotificationService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)
http_bearer_scheme = HTTPBearer(auto_error=False)


def get_app_settings() -> Settings:
    """Dependency providing application settings."""
    return get_settings()


def get_database() -> Database:
    """
    Dependency providing an active MongoDB Database instance.
    Raises HTTP 503 if the database is not configured or unavailable.
    """
    database = db_manager.get_database()
    if database is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is unavailable.",
        )
    return database


def get_user_repository(db: Database = Depends(get_database)) -> UserRepository:
    """Dependency providing UserRepository instance."""
    return UserRepository(db)


def get_upload_repository(db: Database = Depends(get_database)) -> UploadRepository:
    """Dependency providing UploadRepository instance."""
    return UploadRepository(db)


def get_candidate_repository(db: Database = Depends(get_database)) -> CandidateRepository:
    """Dependency providing CandidateRepository instance."""
    return CandidateRepository(db)


def get_pdf_service() -> PDFService:
    """Dependency providing PDFService instance."""
    return PDFService()


def get_parsing_service() -> ParsingService:
    """Dependency providing ParsingService instance."""
    return ParsingService()


@lru_cache
def get_storage_service() -> StorageService:
    """Dependency providing StorageService instance (cached singleton)."""
    return StorageService()


def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repository),
    storage_service: StorageService = Depends(get_storage_service),
) -> AuthService:
    """Dependency providing AuthService instance."""
    return AuthService(user_repo, storage_service)


def get_resume_service(
    upload_repo: UploadRepository = Depends(get_upload_repository),
    pdf_service: PDFService = Depends(get_pdf_service),
    storage_service: StorageService = Depends(get_storage_service),
) -> ResumeService:
    """Dependency providing ResumeService instance."""
    return ResumeService(upload_repo, pdf_service, storage_service)


@lru_cache
def get_embedding_service() -> EmbeddingService:
    """Dependency providing singleton EmbeddingService instance."""
    return EmbeddingService()


def get_candidate_service(
    candidate_repo: CandidateRepository = Depends(get_candidate_repository),
    upload_repo: UploadRepository = Depends(get_upload_repository),
    parsing_service: ParsingService = Depends(get_parsing_service),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> CandidateService:
    """Dependency providing CandidateService instance."""
    return CandidateService(candidate_repo, upload_repo, parsing_service, embedding_service)


def get_search_service(
    candidate_repo: CandidateRepository = Depends(get_candidate_repository),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> SearchService:
    """Dependency providing SearchService instance."""
    return SearchService(candidate_repo, embedding_service)


# --- Chat Dependencies ---

def get_conversation_repository(db: Database = Depends(get_database)) -> ConversationRepository:
    return ConversationRepository(db)

def get_message_repository(db: Database = Depends(get_database)) -> MessageRepository:
    return MessageRepository(db)

def get_notification_repository(db: Database = Depends(get_database)) -> NotificationRepository:
    return NotificationRepository(db)

def get_chat_authorization_service(
    user_repo: UserRepository = Depends(get_user_repository),
    conv_repo: ConversationRepository = Depends(get_conversation_repository),
) -> AuthorizationService:
    return AuthorizationService(user_repo, conv_repo)

def get_conversation_service(
    conv_repo: ConversationRepository = Depends(get_conversation_repository),
    msg_repo: MessageRepository = Depends(get_message_repository),
    auth_service: AuthorizationService = Depends(get_chat_authorization_service),
) -> ConversationService:
    return ConversationService(conv_repo, msg_repo, auth_service)

def get_message_service(
    msg_repo: MessageRepository = Depends(get_message_repository),
    conv_repo: ConversationRepository = Depends(get_conversation_repository),
    auth_service: AuthorizationService = Depends(get_chat_authorization_service),
) -> MessageService:
    return MessageService(msg_repo, conv_repo, auth_service)

def get_notification_service(
    notif_repo: NotificationRepository = Depends(get_notification_repository),
    auth_service: AuthorizationService = Depends(get_chat_authorization_service),
) -> NotificationService:
    return NotificationService(notif_repo, auth_service)


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer_scheme),
    user_repo: UserRepository = Depends(get_user_repository),
) -> UserResponse:
    """
    Dependency extracting and validating the authenticated user from the Bearer JWT.
    Raises HTTP 401 if the token is invalid or user does not exist.
    """
    raw_token = token or (credentials.credentials if credentials else None)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please provide a Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(raw_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: Optional[str] = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_doc = user_repo.find_by_id(user_id)
    if user_doc is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user_doc.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
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


def get_current_admin_user(
    current_user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    """
    Dependency verifying that the authenticated user has admin privileges.
    Raises HTTP 403 FORBIDDEN if user role is not admin.
    """
    if current_user.role.lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required to perform this action.",
        )
    return current_user


class PaginationParams:
    """Common pagination parameters for listing endpoints."""

    def __init__(
        self,
        page: int = Query(default=1, ge=1, description="Page number, 1-indexed"),
        page_size: int = Query(default=10, ge=1, le=100, description="Items per page"),
    ) -> None:
        self.page = page
        self.page_size = page_size
        self.skip = (page - 1) * page_size
        self.limit = page_size
