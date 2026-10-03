import re
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_candidate_repository,
    get_embedding_service,
    get_upload_repository,
)
from app.main import app
from app.models.candidate import CandidateModel
from app.models.upload import UploadModel
from app.services.parsing_service import ParsingService


class FakeCandidateRepository:
    """In-memory CandidateRepository for testing."""

    def __init__(self) -> None:
        self.candidates: Dict[str, Dict[str, Any]] = {}

    def ensure_indexes(self) -> None:
        pass

    def create(self, candidate: CandidateModel) -> Dict[str, Any]:
        doc = candidate.to_mongo()
        doc["_id"] = ObjectId()
        self.candidates[str(doc["_id"])] = doc
        return doc.copy()

    def find_by_id(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        doc = self.candidates.get(str(candidate_id))
        return doc.copy() if doc else None

    def find_by_upload_id(self, upload_id: str) -> Optional[Dict[str, Any]]:
        for doc in self.candidates.values():
            if doc.get("upload_id") == upload_id:
                return doc.copy()
        return None

    def find_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        normalized = email.lower().strip()
        for doc in self.candidates.values():
            if doc.get("email") and doc["email"].lower() == normalized:
                return doc.copy()
        return None

    def list_candidates(
        self,
        skills: Optional[List[str]] = None,
        q: Optional[str] = None,
        skip: int = 0,
        limit: int = 10,
    ) -> Tuple[List[Dict[str, Any]], int]:
        matches = list(self.candidates.values())

        if skills:
            for s in skills:
                matches = [m for m in matches if any(s.lower() == cs.lower() for cs in m.get("skills", []))]

        if q and q.strip():
            term = q.strip().lower()
            matches = [
                m for m in matches
                if term in m.get("full_name", "").lower()
                or term in m.get("title", "").lower()
                or term in m.get("summary", "").lower()
                or any(term in s.lower() for s in m.get("skills", []))
            ]

        total = len(matches)
        return matches[skip : skip + limit], total

    def delete(self, candidate_id: str) -> bool:
        if str(candidate_id) in self.candidates:
            del self.candidates[str(candidate_id)]
            return True
        return False


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
        items = list(self.uploads.values())
        return items[skip : skip + limit], len(items)


@pytest.fixture
def fake_candidate_repo() -> FakeCandidateRepository:
    return FakeCandidateRepository()


@pytest.fixture
def fake_upload_repo() -> FakeUploadRepository:
    repo = FakeUploadRepository()
    resume_text = (
        "Alice Smith\n"
        "Lead Software Architect\n"
        "alice.smith@example.com | +1-555-123-4567 | San Francisco, CA\n\n"
        "Professional Summary\n"
        "Seasoned software architect with 8 years of experience building high-throughput cloud backends.\n\n"
        "Core Skills\n"
        "Python, FastAPI, MongoDB, Docker, Kubernetes, PyMuPDF, AWS, Microservices, CI/CD.\n\n"
        "Education\n"
        "Bachelor of Science in Computer Science, Stanford University\n"
    )
    upload = repo.create(
        UploadModel(
            filename="alice_smith.pdf",
            file_size=120000,
            content_type="application/pdf",
            user_id="test_user",
            page_count=2,
            char_count=len(resume_text),
            status="extracted",
            raw_text=resume_text,
        )
    )
    repo.sample_upload_id = str(upload["_id"])
    return repo


class FakeEmbeddingService:
    """Mock EmbeddingService for deterministic and ultra-fast testing."""

    def __init__(self) -> None:
        self.dimension = 384

    def build_candidate_embedding_text(self, candidate_data: Dict[str, Any]) -> str:
        return "synthetic candidate text"

    def generate_embedding(self, text: str) -> List[float]:
        return [0.05] * 384


@pytest.fixture
def client(
    fake_candidate_repo: FakeCandidateRepository,
    fake_upload_repo: FakeUploadRepository,
) -> TestClient:
    app.dependency_overrides[get_candidate_repository] = lambda: fake_candidate_repo
    app.dependency_overrides[get_upload_repository] = lambda: fake_upload_repo
    app.dependency_overrides[get_embedding_service] = lambda: FakeEmbeddingService()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_parsing_service_extracts_correct_fields() -> None:
    """Unit test deterministic parsing heuristics."""
    parser = ParsingService()
    sample_text = (
        "Bob Developer\n"
        "Senior Backend Engineer\n"
        "bob.dev@gmail.com | (415) 555-0199\n\n"
        "Summary\n"
        "Backend engineer with 5 years experience specializing in Python and PostgreSQL.\n\n"
        "Skills: Python, FastAPI, Docker, PostgreSQL, Redis, REST.\n\n"
        "Education: Master of Science in Software Engineering\n"
    )

    parsed = parser.parse_resume_text(sample_text)
    assert parsed["full_name"] == "Bob Developer"
    assert parsed["email"] == "bob.dev@gmail.com"
    assert "415" in parsed["phone"]
    assert parsed["title"] == "Senior Backend Engineer"
    assert "Python" in parsed["skills"]
    assert "FastAPI" in parsed["skills"]
    assert "PostgreSQL" in parsed["skills"]
    assert parsed["experience_years"] == 5.0
    assert any("Master" in edu for edu in parsed["education"])


def test_experience_calculation_from_date_ranges() -> None:
    """Verify calculating experience years from chronological job date ranges."""
    parser = ParsingService()
    # Resume WITHOUT explicit "X years" statement
    resume_with_dates = (
        "Jane Engineer\n"
        "Lead Backend Architect\n\n"
        "Experience:\n"
        "Staff Engineer at TechCorp\n"
        "Jan 2021 - Dec 2023\n\n"
        "Senior Developer at StartupX\n"
        "Jan 2018 - Dec 2020\n"
    )
    # Jan 2018 to Dec 2020 = 3.0 yrs; Jan 2021 to Dec 2023 = 3.0 yrs -> Total ~ 6.0 yrs
    years = parser.extract_experience_years(resume_with_dates)
    assert years is not None
    assert 5.8 <= years <= 6.2


def test_experience_calculation_merges_overlapping_dates() -> None:
    """Verify concurrent/overlapping job dates are merged and not double-counted."""
    parser = ParsingService()
    # Job 1: 2020 - 2022 (2 yrs), Job 2: 2021 - 2023 (2 yrs) -> Continuous 2020 - 2023 = ~3-4 yrs
    resume_overlap = (
        "Consultant Developer\n"
        "Company A: 2020 - 2022\n"
        "Company B (Part-time): 2021 - 2023\n"
    )
    years = parser.extract_experience_years(resume_overlap)
    assert years is not None
    assert 3.0 <= years <= 4.0


def test_parse_and_create_candidate_from_upload(
    client: TestClient,
    fake_upload_repo: FakeUploadRepository,
) -> None:
    """Test parsing an uploaded resume and persisting candidate profile."""
    upload_id = fake_upload_repo.sample_upload_id

    response = client.post(f"/api/candidates/parse/{upload_id}")
    assert response.status_code == 201

    data = response.json()
    assert data["full_name"] == "Alice Smith"
    assert data["email"] == "alice.smith@example.com"
    assert data["title"] == "Lead Software Architect"
    assert "Python" in data["skills"]
    assert "FastAPI" in data["skills"]
    assert "MongoDB" in data["skills"]
    assert data["experience_years"] == 8.0
    assert data["upload_id"] == upload_id
    assert "id" in data


def test_parse_candidate_idempotent(
    client: TestClient,
    fake_upload_repo: FakeUploadRepository,
) -> None:
    """Test re-parsing same upload returns existing candidate."""
    upload_id = fake_upload_repo.sample_upload_id

    res1 = client.post(f"/api/candidates/parse/{upload_id}")
    assert res1.status_code == 201
    cid1 = res1.json()["id"]

    res2 = client.post(f"/api/candidates/parse/{upload_id}")
    assert res2.status_code == 201
    cid2 = res2.json()["id"]

    assert cid1 == cid2


def test_list_candidates_with_skill_filter(
    client: TestClient,
    fake_upload_repo: FakeUploadRepository,
) -> None:
    """Test querying candidates with skills filter."""
    upload_id = fake_upload_repo.sample_upload_id
    client.post(f"/api/candidates/parse/{upload_id}")

    # Query with matching skill
    res = client.get("/api/candidates?skills=FastAPI")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert "FastAPI" in data["items"][0]["skills"]

    # Query with non-matching skill
    res_none = client.get("/api/candidates?skills=Swift")
    assert res_none.status_code == 200
    assert res_none.json()["total"] == 0


def test_get_candidate_by_id(
    client: TestClient,
    fake_upload_repo: FakeUploadRepository,
) -> None:
    """Test fetching candidate details by ID."""
    upload_id = fake_upload_repo.sample_upload_id
    create_res = client.post(f"/api/candidates/parse/{upload_id}")
    candidate_id = create_res.json()["id"]

    get_res = client.get(f"/api/candidates/{candidate_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == candidate_id
    assert get_res.json()["full_name"] == "Alice Smith"


def test_delete_candidate(
    client: TestClient,
    fake_upload_repo: FakeUploadRepository,
) -> None:
    """Test deleting candidate profile."""
    upload_id = fake_upload_repo.sample_upload_id
    create_res = client.post(f"/api/candidates/parse/{upload_id}")
    candidate_id = create_res.json()["id"]

    del_res = client.delete(f"/api/candidates/{candidate_id}")
    assert del_res.status_code == 204

    # Verify deleted
    get_res = client.get(f"/api/candidates/{candidate_id}")
    assert get_res.status_code == 404


def test_list_candidates_pagination(
    client: TestClient,
    fake_candidate_repo: FakeCandidateRepository,
) -> None:
    """Test pagination behavior with page, page_size, total_pages, has_next, and has_prev."""
    # Seed 15 dummy candidates
    for i in range(1, 16):
        cand = CandidateModel(
            full_name=f"Candidate {i}",
            email=f"candidate{i}@example.com",
            title="Software Engineer",
            skills=["Python", "FastAPI"],
            experience_years=float(i),
        )
        fake_candidate_repo.create(cand)

    # Page 1 with page_size=5
    res1 = client.get("/api/candidates?page=1&page_size=5")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["total"] == 15
    assert data1["page"] == 1
    assert data1["page_size"] == 5
    assert data1["total_pages"] == 3
    assert data1["has_next"] is True
    assert data1["has_prev"] is False
    assert len(data1["items"]) == 5

    # Page 2 with page_size=5
    res2 = client.get("/api/candidates?page=2&page_size=5")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["page"] == 2
    assert data2["total_pages"] == 3
    assert data2["has_next"] is True
    assert data2["has_prev"] is True
    assert len(data2["items"]) == 5

    # Page 3 (last page) with page_size=5
    res3 = client.get("/api/candidates?page=3&page_size=5")
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["page"] == 3
    assert data3["total_pages"] == 3
    assert data3["has_next"] is False
    assert data3["has_prev"] is True
    assert len(data3["items"]) == 5

