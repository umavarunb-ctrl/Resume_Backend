from typing import Any, Dict, Optional
from bson import ObjectId
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_user_repository, get_storage_service
from app.services.storage_service import StorageService
from unittest.mock import MagicMock
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.user import UserModel


class FakeUserRepository:
    """In-memory UserRepository for unit & integration testing."""

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
    user = repo.create(
        UserModel(
            email="me@example.com",
            full_name="Me Recruiter",
            hashed_password=hash_password("Password123!"),
            role="recruiter",
            profile_picture="https://example.com/me.jpg",
            company_name="Acme Corp",
            is_active=True,
        )
    )
    inactive_user = repo.create(
        UserModel(
            email="inactive_me@example.com",
            full_name="Inactive Me",
            hashed_password=hash_password("Password123!"),
            role="recruiter",
            is_active=False,
        )
    )
    repo.seeded_user_id = str(user["_id"])
    repo.inactive_user_id = str(inactive_user["_id"])
    return repo


@pytest.fixture
def fake_storage_service() -> MagicMock:
    mock = MagicMock(spec=StorageService)
    mock.enabled = True
    mock.generate_presigned_url.return_value = "https://objectstorage.test/p/avatar"
    return mock


@pytest.fixture
def client(fake_repo: FakeUserRepository, fake_storage_service: MagicMock) -> TestClient:
    app.dependency_overrides[get_user_repository] = lambda: fake_repo
    app.dependency_overrides[get_storage_service] = lambda: fake_storage_service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_get_current_user_me_success(client: TestClient, fake_repo: FakeUserRepository) -> None:
    """Verify GET /api/users/me returns the authenticated user's profile with company and avatar."""
    token = create_access_token({"sub": fake_repo.seeded_user_id, "email": "me@example.com"})

    response = client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == fake_repo.seeded_user_id
    assert data["email"] == "me@example.com"
    assert data["full_name"] == "Me Recruiter"
    assert data["role"] == "recruiter"
    assert data["profile_picture"] == "https://example.com/me.jpg"
    assert data["company_name"] == "Acme Corp"
    assert data["is_active"] is True


def test_update_user_profile_success(client: TestClient, fake_repo: FakeUserRepository) -> None:
    """Verify PUT /api/users/me updates profile picture, company name, and full name."""
    token = create_access_token({"sub": fake_repo.seeded_user_id, "email": "me@example.com"})
    update_payload = {
        "full_name": "Updated Recruiter Name",
        "profile_picture": "https://example.com/new_avatar.png",
        "company_name": "Global Tech Talent",
    }

    response = client.put(
        "/api/users/me",
        json=update_payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["full_name"] == "Updated Recruiter Name"
    assert data["profile_picture"] == "https://example.com/new_avatar.png"
    assert data["company_name"] == "Global Tech Talent"

def test_upload_profile_picture_success(client: TestClient, fake_repo: FakeUserRepository, fake_storage_service: MagicMock) -> None:
    """Verify POST /api/users/me/profile-picture uploads a file and returns OCI URL."""
    token = create_access_token({"sub": fake_repo.seeded_user_id, "email": "me@example.com"})
    
    import io
    # Create fake image bytes
    image_bytes = b"fake_image_content"
    
    response = client.post(
        "/api/users/me/profile-picture",
        files={"file": ("avatar.jpg", io.BytesIO(image_bytes), "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["profile_picture"] == "https://objectstorage.test/p/avatar"
    fake_storage_service.upload_file.assert_called_once()
    
    # Check that in DB it is stored as oci:
    user_in_db = fake_repo.find_by_id(fake_repo.seeded_user_id)
    assert user_in_db["profile_picture"].startswith("oci:profile_pictures/")


def test_get_current_user_me_unauthorized_no_token(client: TestClient) -> None:
    """Verify GET /api/users/me returns 401 when no token is provided."""
    response = client.get("/api/users/me")
    assert response.status_code == 401


def test_get_current_user_me_invalid_token(client: TestClient) -> None:
    """Verify GET /api/users/me returns 401 when invalid token is provided."""
    response = client.get(
        "/api/users/me",
        headers={"Authorization": "Bearer invalid.token.value"},
    )
    assert response.status_code == 401


def test_get_current_user_me_inactive_user(client: TestClient, fake_repo: FakeUserRepository) -> None:
    """Verify GET /api/users/me returns 403 when user is marked inactive."""
    token = create_access_token({"sub": fake_repo.inactive_user_id, "email": "inactive_me@example.com"})

    response = client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert "inactive" in response.json()["detail"]
