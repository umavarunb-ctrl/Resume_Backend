import io
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_upload_repository, get_storage_service
from app.main import app
from app.models.upload import UploadModel
from app.services.storage_service import StorageService
from unittest.mock import MagicMock


class FakeUploadRepository:
    """In-memory UploadRepository for testing."""

    def __init__(self) -> None:
        self.uploads: Dict[str, Dict[str, Any]] = {}

    def ensure_indexes(self) -> None:
        pass

    def create(self, upload: UploadModel) -> Dict[str, Any]:
        doc = upload.to_mongo()
        doc["_id"] = ObjectId()
        self.uploads[str(doc["_id"])] = doc
        return doc.copy()

    def find_by_id(self, upload_id: str) -> Optional[Dict[str, Any]]:
        doc = self.uploads.get(str(upload_id))
        return doc.copy() if doc else None

    def find_by_user(
        self,
        user_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 10,
    ) -> Tuple[List[Dict[str, Any]], int]:
        if user_id:
            matches = [d.copy() for d in self.uploads.values() if d.get("user_id") == user_id]
        else:
            matches = [d.copy() for d in self.uploads.values()]
        total = len(matches)
        total = len(matches)
        return matches[skip : skip + limit], total

    def delete(self, upload_id: str) -> bool:
        doc = self.uploads.pop(str(upload_id), None)
        return doc is not None

def make_pdf(text: str) -> bytes:
    """Generate in-memory PDF with selectable text using PyMuPDF."""
    doc = pymupdf.open()
    page = doc.new_page()
    if text:
        page.insert_text((50, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture
def fake_upload_repo() -> FakeUploadRepository:
    return FakeUploadRepository()


@pytest.fixture
def fake_storage_service() -> MagicMock:
    mock = MagicMock(spec=StorageService)
    mock.enabled = True
    mock.bucket_name = "test_bucket"
    mock.generate_object_name.return_value = "resumes/2026/10/test.pdf"
    mock.generate_presigned_url.return_value = "https://objectstorage.test/p/url"
    return mock


@pytest.fixture
def client(fake_upload_repo: FakeUploadRepository, fake_storage_service: MagicMock) -> TestClient:
    app.dependency_overrides[get_upload_repository] = lambda: fake_upload_repo
    app.dependency_overrides[get_storage_service] = lambda: fake_storage_service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_upload_valid_resume_pdf_without_auth(client: TestClient, fake_storage_service: MagicMock) -> None:
    """Test successful upload of a selectable-text PDF resume without auth bearer token."""
    resume_text = (
        "Alice Smith - Lead Software Architect\n"
        "Experience: 8+ years developing scalable Python backends with FastAPI and MongoDB.\n"
        "Skills: Python, FastAPI, MongoDB, Docker, Microservices, PyMuPDF, Machine Learning."
    )
    pdf_bytes = make_pdf(resume_text)

    # Note: No Authorization header passed!
    response = client.post(
        "/api/uploads/resume",
        files={"file": ("alice_smith_resume.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    if response.status_code != 201:
        print(response.json())
    assert response.status_code == 201

    data = response.json()
    assert data["upload_id"] is not None
    assert "Alice Smith" in data["full_name"]
    assert "Python" in data["skills"]
    assert "upload_id" in data
    fake_storage_service.upload_file.assert_called_once()

def test_upload_mongo_failure_rollback(client: TestClient, fake_upload_repo: FakeUploadRepository, fake_storage_service: MagicMock) -> None:
    resume_text = "Test Resume"
    pdf_bytes = make_pdf(resume_text)

    # Make Mongo create fail
    fake_upload_repo.create = MagicMock(side_effect=Exception("MongoDB error"))

    response = client.post(
        "/api/uploads/resume",
        files={"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    if response.status_code != 500:
        print("MongoDB error test failed:", response.json())
    assert response.status_code == 500
    fake_storage_service.upload_file.assert_called_once()
    fake_storage_service.delete_file.assert_called_once()

def test_upload_non_pdf_file_rejected(client: TestClient) -> None:
    """Test uploading a non-PDF file (.txt) returns 400."""
    response = client.post(
        "/api/uploads/resume",
        files={"file": ("resume.txt", io.BytesIO(b"Hello world"), "text/plain")},
    )
    assert response.status_code == 400
    assert "Only PDF documents" in response.json()["detail"]


def test_upload_blank_pdf_rejected(client: TestClient) -> None:
    """Test uploading a PDF without selectable text returns 400."""
    blank_pdf = make_pdf("")
    response = client.post(
        "/api/uploads/resume",
        files={"file": ("blank_resume.pdf", io.BytesIO(blank_pdf), "application/pdf")},
    )
    assert response.status_code == 400
    assert "No selectable text" in response.json()["detail"]


def test_get_upload_detail_without_auth(client: TestClient) -> None:
    """Test retrieving full extracted text for an upload without auth bearer token."""
    resume_text = "Bob Jones - Senior Backend Developer with 5 years experience in Python and Atlas."
    pdf_bytes = make_pdf(resume_text)

    upload_res = client.post(
        "/api/uploads/resume",
        files={"file": ("bob_resume.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert upload_res.status_code == 201
    file_id = upload_res.json()["upload_id"]

    # Request without Authorization header
    detail_res = client.get(f"/api/uploads/{file_id}")
    assert detail_res.status_code == 200

    data = detail_res.json()
    assert data["file_id"] == file_id
    assert "Bob Jones" in data["raw_text"]
    assert data["filename"] == "bob_resume.pdf"


def test_get_upload_detail_not_found(client: TestClient) -> None:
    """Test requesting a non-existent file_id returns 404."""
    response = client.get("/api/uploads/60c72b2f9b1d8b2bad999999")
    assert response.status_code == 404


def test_list_uploads_without_auth(client: TestClient) -> None:
    """Test listing paginated uploads without auth bearer token."""
    for name in ["resume_one", "resume_two"]:
        pdf = make_pdf(f"Candidate {name} with long experience in cloud services.")
        client.post(
            "/api/uploads/resume",
            files={"file": (f"{name}.pdf", io.BytesIO(pdf), "application/pdf")},
        )

    response = client.get("/api/uploads?page=1&page_size=10")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] >= 2
    assert len(data["items"]) >= 2
    assert data["page"] == 1

def test_get_download_url(client: TestClient, fake_upload_repo: FakeUploadRepository, fake_storage_service: MagicMock) -> None:
    # Setup
    fake_upload_repo.uploads["test_id"] = {
        "_id": ObjectId(),
        "object_name": "resumes/2026/10/test.pdf",
        "user_id": "test_user"
    }

    # Request without auth
    response = client.get("/api/uploads/test_id/download")
    assert response.status_code == 200
    assert response.json()["url"] == "https://objectstorage.test/p/url"
    fake_storage_service.generate_presigned_url.assert_called_once_with("resumes/2026/10/test.pdf")

def test_delete_upload(client: TestClient, fake_upload_repo: FakeUploadRepository, fake_storage_service: MagicMock) -> None:
    # Setup
    fake_upload_repo.uploads["test_id"] = {
        "_id": ObjectId(),
        "object_name": "resumes/2026/10/test.pdf",
        "user_id": "test_user"
    }

    response = client.delete("/api/uploads/test_id")
    assert response.status_code == 204
    assert "test_id" not in fake_upload_repo.uploads
    fake_storage_service.delete_file.assert_called_once_with("resumes/2026/10/test.pdf")
