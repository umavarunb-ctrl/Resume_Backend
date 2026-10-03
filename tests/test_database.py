from unittest.mock import patch
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.database import db_manager
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.main import app

client = TestClient(app)


def test_database_health_healthy() -> None:
    """Verify /api/health/database returns 200 when database ping succeeds."""
    with patch.object(db_manager, "ping", return_value=(True, "connected")):
        response = client.get("/api/health/database")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy", "database": "connected"}


def test_database_health_unhealthy() -> None:
    """Verify /api/health/database returns 503 when database ping fails."""
    with patch.object(db_manager, "ping", return_value=(False, "Database unreachable")):
        response = client.get("/api/health/database")
        assert response.status_code == 503
        assert response.json() == {"status": "unhealthy", "database": "disconnected"}


def test_database_ping_unconfigured() -> None:
    """Verify database ping returns False gracefully when MONGODB_URI is not set."""
    with patch("app.core.database.settings.MONGODB_URI", ""):
        is_healthy, message = db_manager.ping()
        assert is_healthy is False
        assert "not configured" in message


def test_security_password_hashing() -> None:
    """Verify bcrypt password hashing and verification utilities."""
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_security_jwt_token_lifecycle() -> None:
    """Verify JWT access token generation and decoding."""
    payload = {"sub": "user_12345", "role": "recruiter"}
    token = create_access_token(payload)

    assert isinstance(token, str)
    decoded = decode_access_token(token)

    assert decoded is not None
    assert decoded["sub"] == "user_12345"
    assert decoded["role"] == "recruiter"
    assert "exp" in decoded
    assert "iat" in decoded


def test_security_jwt_invalid_token() -> None:
    """Verify invalid JWT returns None."""
    decoded = decode_access_token("invalid.token.structure")
    assert decoded is None


def test_cors_origins_parsing() -> None:
    """Verify comma-separated CORS_ORIGINS parsing."""
    test_settings = Settings(CORS_ORIGINS="http://localhost:3000, http://localhost:5173, https://app.example.com")
    assert test_settings.cors_origins_list == [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://app.example.com",
    ]
