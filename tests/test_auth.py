from datetime import datetime, timezone
from typing import Any, Dict, Optional
from bson import ObjectId
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_user_repository
from app.core.security import hash_password
from app.main import app
from app.models.user import UserModel


class FakeUserRepository:
    """In-memory UserRepository for unit & integration testing without live MongoDB."""

    def __init__(self) -> None:
        self.users: Dict[str, Dict[str, Any]] = {}

    def ensure_indexes(self) -> None:
        pass

    def find_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        normalized = email.lower().strip()
        for doc in self.users.values():
            if doc["email"] == normalized:
                return doc.copy()
        return None

    def find_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        doc = self.users.get(str(user_id))
        return doc.copy() if doc else None

    def create(self, user: UserModel) -> Dict[str, Any]:
        doc = user.to_mongo()
        doc["_id"] = ObjectId()
        doc["email"] = doc["email"].lower().strip()
        self.users[str(doc["_id"])] = doc
        return doc.copy()

    def update_user(self, user_id: str, update_fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if str(user_id) in self.users:
            self.users[str(user_id)].update(update_fields)
            return self.users[str(user_id)].copy()
        return None


@pytest.fixture
def fake_repo() -> FakeUserRepository:
    repo = FakeUserRepository()
    # Seed an existing user
    repo.create(
        UserModel(
            email="existing@example.com",
            full_name="Existing User",
            hashed_password=hash_password("ExistingPassword123!"),
            role="recruiter",
            is_active=True,
        )
    )
    # Seed an inactive user
    repo.create(
        UserModel(
            email="inactive@example.com",
            full_name="Inactive User",
            hashed_password=hash_password("InactivePassword123!"),
            role="recruiter",
            is_active=False,
        )
    )
    return repo


@pytest.fixture
def client(fake_repo: FakeUserRepository) -> TestClient:
    app.dependency_overrides[get_user_repository] = lambda: fake_repo
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_register_success(client: TestClient) -> None:
    """Test successful user registration."""
    payload = {
        "email": "newrecruiter@example.com",
        "password": "Password123!",
        "full_name": "New Recruiter",
        "role": "recruiter",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["email"] == "newrecruiter@example.com"
    assert data["full_name"] == "New Recruiter"
    assert data["role"] == "recruiter"
    assert data["is_active"] is True
    assert "id" in data
    assert "hashed_password" not in data


def test_register_duplicate_email(client: TestClient) -> None:
    """Test registration with existing email returns 400."""
    payload = {
        "email": "existing@example.com",
        "password": "Password123!",
        "full_name": "Duplicate User",
        "role": "recruiter",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_register_short_password(client: TestClient) -> None:
    """Test registration with password under 8 characters fails validation."""
    payload = {
        "email": "short@example.com",
        "password": "short",
        "full_name": "Short Pass",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 422


def test_login_success(client: TestClient) -> None:
    """Test successful login returns JWT access token."""
    payload = {
        "email": "existing@example.com",
        "password": "ExistingPassword123!",
    }
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


def test_login_invalid_password(client: TestClient) -> None:
    """Test login with wrong password returns 401."""
    payload = {
        "email": "existing@example.com",
        "password": "WrongPassword123!",
    }
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_login_nonexistent_user(client: TestClient) -> None:
    """Test login with non-existent email returns 401."""
    payload = {
        "email": "ghost@example.com",
        "password": "AnyPassword123!",
    }
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 401


def test_login_inactive_user(client: TestClient) -> None:
    """Test login with inactive account returns 403."""
    payload = {
        "email": "inactive@example.com",
        "password": "InactivePassword123!",
    }
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 403
    assert "inactive" in response.json()["detail"]


def test_logout_success(client: TestClient) -> None:
    """Test logout endpoint returns 200 and success message."""
    response = client.post("/api/auth/logout")
    assert response.status_code == 200
    assert response.json()["message"] == "Successfully logged out."


def test_forgot_and_reset_password_success(client: TestClient) -> None:
    """Test full forgot-password and reset-password flow."""
    # 1. Request reset token
    forgot_resp = client.post("/api/auth/forgot-password", json={"email": "existing@example.com"})
    assert forgot_resp.status_code == 200
    data = forgot_resp.json()
    assert "reset_token" in data
    assert data["reset_token"] is not None
    reset_token = data["reset_token"]

    # 2. Reset password using token
    reset_resp = client.post(
        "/api/auth/reset-password",
        json={"reset_token": reset_token, "new_password": "BrandNewPassword123!"},
    )
    assert reset_resp.status_code == 200
    assert "successfully reset" in reset_resp.json()["message"]

    # 3. Verify login works with new password
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "existing@example.com", "password": "BrandNewPassword123!"},
    )
    assert login_resp.status_code == 200


def test_reset_password_invalid_token(client: TestClient) -> None:
    """Test resetting password with invalid token returns 400."""
    response = client.post(
        "/api/auth/reset-password",
        json={"reset_token": "invalid.token.value", "new_password": "NewPassword123!"},
    )
    assert response.status_code == 400
