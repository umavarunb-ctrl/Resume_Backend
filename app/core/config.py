from functools import lru_cache
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables and .env file."""

    APP_NAME: str = "Recruiter Resume Search API"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"

    # Database
    MONGODB_URI: str = "mongodb+srv://rockyrocky77rockyy_db_user:T1ajjz6w33PArOPc@resumeram.escw0k2.mongodb.net"
    MONGODB_DATABASE: str = "resume_ramcharan"

    # Security & JWT
    JWT_SECRET: str = "replace-with-a-long-random-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    CORS_ORIGINS: str = "http://localhost:8080,http://127.0.0.1:8080,http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173,https://atsflow.syncrotech.online"
    CORS_ORIGIN_REGEX: Optional[str] = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$|^https://atsflow\.syncrotech\.online$"

    # Embeddings & Uploads
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    MAX_UPLOAD_SIZE_MB: int = 10

    # Oracle Cloud Infrastructure (OCI) Object Storage
    OCI_TENANCY_OCID: Optional[str] = None
    OCI_USER_OCID: Optional[str] = None
    OCI_FINGERPRINT: Optional[str] = None
    OCI_REGION: Optional[str] = None
    OCI_NAMESPACE: Optional[str] = None
    OCI_BUCKET_NAME: Optional[str] = None
    OCI_PRIVATE_KEY_PATH: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse comma-separated CORS_ORIGINS into a clean list of allowed origins."""
        if not self.CORS_ORIGINS:
            return []
        return [
            origin.strip()
            for origin in self.CORS_ORIGINS.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    """Return cached instance of application settings."""
    return Settings()


settings: Settings = get_settings()
