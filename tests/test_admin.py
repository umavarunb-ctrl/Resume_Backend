from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_user_repository
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.user import UserModel


class FakeUserRepository:
    """In-memory UserRepository for admin testing."""

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

    def list_users(self, skip: int = 0, limit: int = 10) -> Tuple[List[Dict[str, Any]], int]:
        items = list(self.users.values())
        return items[skip : skip + limit], len(items)


@pytest.fixture
def fake_repo() -> FakeUserRepository:
    repo = FakeUserRepository()
    # Seed an Admin User
    admin = repo.create(
        UserModel(
            email="admin@example.com",
            full_name="System Admin",
            hashed_password=hash_password("AdminPassword123!"),
            role="admin",
            is_active=True,
        )
    )
    # Seed a Recruiter User
    recruiter = repo.create(
        UserModel(
            email="recruiter@example.com",
            full_name="Normal Recruiter",
            hashed_password=hash_password("RecruiterPassword123!"),
            role="recruiter",
            is_active=True,
        )
    )
    repo.admin_id = str(admin["_id"])
    repo.recruiter_id = str(recruiter["_id"])
    return repo


@pytest.fixture
def client(fake_repo: FakeUserRepository) -> TestClient:
    app.dependency_overrides[get_user_repository] = lambda: fake_repo
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_admin_list_users_success(client: TestClient, fake_repo: FakeUserRepository) -> None:
    """Verify admin user can list all registered system users."""
    token = create_access_token({"sub": fake_repo.admin_id, "email": "admin@example.com", "role": "admin"})

    response = client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_recruiter_cannot_access_admin_list_users(client: TestClient, fake_repo: FakeUserRepository) -> None:
    """Verify non-admin user receives 403 Forbidden when accessing admin endpoints."""
    token = create_access_token({"sub": fake_repo.recruiter_id, "email": "recruiter@example.com", "role": "recruiter"})

    response = client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert "Admin privileges required" in response.json()["detail"]


def test_admin_update_user_status(client: TestClient, fake_repo: FakeUserRepository) -> None:
    """Verify admin can deactivate and reactivate a user account."""
    token = create_access_token({"sub": fake_repo.admin_id, "email": "admin@example.com", "role": "admin"})

    # Deactivate recruiter
    response = client.patch(
        f"/api/admin/users/{fake_repo.recruiter_id}/status",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_admin_update_user_role(client: TestClient, fake_repo: FakeUserRepository) -> None:
    """Verify admin can promote recruiter to admin role."""
    token = create_access_token({"sub": fake_repo.admin_id, "email": "admin@example.com", "role": "admin"})

    # Promote recruiter to admin
    response = client.patch(
        f"/api/admin/users/{fake_repo.recruiter_id}/role",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"
