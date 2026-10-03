from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_candidate_repository, get_embedding_service
from app.main import app
from app.models.candidate import CandidateModel
from app.services.search_service import SearchService


class FakeCandidateRepository:
    """In-memory CandidateRepository for search testing."""

    def __init__(self) -> None:
        self.candidates: Dict[str, Dict[str, Any]] = {}
        # Expose a mock collection object that mimics find and aggregate
        self.collection = self

    def _match_doc(self, doc: Dict[str, Any], condition: Dict[str, Any]) -> bool:
        for key, val in condition.items():
            if key == "$or":
                if not any(self._match_doc(doc, sub) for sub in val):
                    return False
            elif key == "$and":
                if not all(self._match_doc(doc, sub) for sub in val):
                    return False
            elif key == "experience_years":
                exp = doc.get("experience_years")
                if val is None:
                    if exp is not None:
                        return False
                elif isinstance(val, dict):
                    if "$exists" in val and val["$exists"] is False:
                        if "experience_years" in doc and doc["experience_years"] is not None:
                            return False
                        continue
                    if exp is None:
                        return False
                    if "$gte" in val and exp < val["$gte"]:
                        return False
                    if "$lte" in val and exp > val["$lte"]:
                        return False
            elif key == "title" and isinstance(val, dict) and "$regex" in val:
                pattern = val["$regex"].strip("^$")
                import re
                if not re.search(pattern, doc.get("title") or "", re.IGNORECASE):
                    return False
            elif key == "skills" and isinstance(val, dict) and "$regex" in val:
                pattern = val["$regex"].strip("^$")
                if not any(pattern.lower() == s.lower() for s in doc.get("skills", [])):
                    return False
        return True

    def find(self, query: Dict[str, Any], projection: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not query:
            return list(self.candidates.values())
        return [doc for doc in self.candidates.values() if self._match_doc(doc, query)]

    def aggregate(self, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Trigger fallback to test resilience
        from pymongo.errors import OperationFailure
        raise OperationFailure("PlanExecutor error: vector index not found")

    def create(self, candidate: CandidateModel) -> Dict[str, Any]:
        doc = candidate.to_mongo()
        doc["_id"] = ObjectId()
        self.candidates[str(doc["_id"])] = doc
        return doc.copy()


class FakeEmbeddingService:
    """Deterministic embedding service producing known vectors for predictable similarity."""

    def __init__(self) -> None:
        self.dimension = 384

    def generate_embedding(self, text: str) -> List[float]:
        # Generate predictable vector based on keywords
        vec = [0.0] * self.dimension
        lower = text.lower()
        if "python" in lower or "fastapi" in lower or "backend" in lower:
            # High weight on first component
            vec[0] = 0.9
            vec[1] = 0.435
        elif "react" in lower or "frontend" in lower:
            # High weight on second component
            vec[0] = 0.1
            vec[1] = 0.99
        else:
            vec[0] = 0.5
            vec[1] = 0.5
        return vec


@pytest.fixture
def fake_candidate_repo() -> FakeCandidateRepository:
    repo = FakeCandidateRepository()
    # Candidate 1: Senior Backend Engineer (Python, FastAPI)
    repo.create(
        CandidateModel(
            full_name="Alice Backend",
            email="alice@example.com",
            title="Senior Backend Engineer",
            skills=["Python", "FastAPI", "MongoDB", "Docker"],
            experience_years=8.0,
            summary="Experienced in Python microservices and high-throughput APIs.",
            embedding=[0.9, 0.435] + [0.0] * 382,
        )
    )
    # Candidate 2: Frontend Developer (React, Next.js)
    repo.create(
        CandidateModel(
            full_name="Bob Frontend",
            email="bob@example.com",
            title="Frontend Developer",
            skills=["React", "Next.js", "TypeScript", "CSS"],
            experience_years=3.0,
            summary="Specializing in responsive web UI with React.",
            embedding=[0.1, 0.99] + [0.0] * 382,
        )
    )
    # Candidate 3: Junior Developer (Python)
    repo.create(
        CandidateModel(
            full_name="Charlie Junior",
            email="charlie@example.com",
            title="Junior Software Engineer",
            skills=["Python"],
            experience_years=1.0,
            summary="Junior developer with basic Python knowledge.",
            embedding=[0.6, 0.3] + [0.0] * 382,
        )
    )
    # Candidate 4: Unstated Experience Candidate (Java, JavaScript)
    repo.create(
        CandidateModel(
            full_name="David Unstated",
            email="david@example.com",
            title="Software Developer",
            skills=["Java", "JavaScript", "Python"],
            experience_years=None,
            summary="Full stack engineer.",
            embedding=[0.5, 0.5] + [0.0] * 382,
        )
    )
    return repo


@pytest.fixture
def client(fake_candidate_repo: FakeCandidateRepository) -> TestClient:
    app.dependency_overrides[get_candidate_repository] = lambda: fake_candidate_repo
    app.dependency_overrides[get_embedding_service] = lambda: FakeEmbeddingService()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_cosine_similarity_calculation() -> None:
    """Verify cosine similarity mathematical properties."""
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]

    # Identical vectors -> 1.0
    assert pytest.approx(SearchService.cosine_similarity(v1, v2), 0.001) == 1.0
    # Orthogonal vectors -> 0.0
    assert pytest.approx(SearchService.cosine_similarity(v1, v3), 0.001) == 0.0
    # Empty vectors -> 0.0
    assert SearchService.cosine_similarity([], []) == 0.0


def test_semantic_search_endpoint(client: TestClient) -> None:
    """Verify POST /api/search/semantic returns ranked candidates."""
    payload = {
        "query": "Senior Python Backend Developer with FastAPI experience",
        "limit": 5,
        "min_score": 0.0,
    }
    response = client.post("/api/search/semantic", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["search_type"] == "semantic"
    assert data["total_matches"] >= 2
    assert len(data["results"]) >= 2

    # Alice Backend should rank first due to vector similarity
    top_result = data["results"][0]
    assert top_result["candidate"]["full_name"] == "Alice Backend"
    assert top_result["score"] > 0.8
    assert top_result["match_type"] == "semantic"


def test_hybrid_search_with_experience_filter(client: TestClient) -> None:
    """Verify hybrid search correctly applies min_experience_years filter."""
    payload = {
        "query": "Python Developer",
        "filters": {
            "min_experience_years": 4.0,
        },
        "vector_weight": 0.7,
        "limit": 5,
    }
    response = client.post("/api/search/hybrid", json=payload)
    assert response.status_code == 200

    data = response.json()
    # Charlie Junior (1 yr) and David Unstated (None) should be filtered out; Alice Backend (8 yrs) must remain
    names = [r["candidate"]["full_name"] for r in data["results"]]
    assert "Alice Backend" in names
    assert "Charlie Junior" not in names
    assert "David Unstated" not in names


def test_enterprise_hybrid_search_min_exp_zero_includes_null_exp(client: TestClient) -> None:
    """Verify enterprise logic: min_experience_years=0 includes unstated (null) experience candidates."""
    payload = {
        "query": "Software Engineer",
        "filters": {
            "min_experience_years": 0.0,
        },
        "vector_weight": 0.5,
        "limit": 10,
    }
    response = client.post("/api/search/hybrid", json=payload)
    assert response.status_code == 200

    data = response.json()
    names = [r["candidate"]["full_name"] for r in data["results"]]
    assert "David Unstated" in names
    assert "Alice Backend" in names
    assert "Bob Frontend" in names


def test_enterprise_hybrid_search_skill_match_mode_any(client: TestClient) -> None:
    """Verify skill_match_mode 'any' matches candidates possessing at least one skill."""
    payload = {
        "query": "Software Engineer",
        "filters": {
            "skills": ["React", "FastAPI"],
            "skill_match_mode": "any",
        },
        "vector_weight": 0.5,
        "limit": 10,
    }
    response = client.post("/api/search/hybrid", json=payload)
    assert response.status_code == 200

    data = response.json()
    names = [r["candidate"]["full_name"] for r in data["results"]]
    assert "Bob Frontend" in names  # Has React
    assert "Alice Backend" in names  # Has FastAPI


def test_hybrid_search_with_skills_filter(client: TestClient) -> None:
    """Verify hybrid search with hard required skills (default 'all' mode)."""
    payload = {
        "query": "Software Engineer",
        "filters": {
            "skills": ["React"],
            "skill_match_mode": "all",
        },
        "vector_weight": 0.5,
    }
    response = client.post("/api/search/hybrid", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["total_matches"] == 1
    assert data["results"][0]["candidate"]["full_name"] == "Bob Frontend"
    assert "React" in data["results"][0]["matched_skills"]


def test_search_query_validation(client: TestClient) -> None:
    """Verify query with less than 2 characters returns 422."""
    response = client.post("/api/search/semantic", json={"query": "a"})
    assert response.status_code == 422

