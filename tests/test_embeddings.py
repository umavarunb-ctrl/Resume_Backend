from unittest.mock import MagicMock, patch
import pytest

from app.services.embedding_service import EmbeddingService


def test_embedding_service_build_candidate_text() -> None:
    """Verify synthesis of candidate fields into a dense semantic string."""
    service = EmbeddingService()
    candidate_data = {
        "title": "Lead Software Architect",
        "skills": ["Python", "FastAPI", "MongoDB"],
        "experience_years": 8.0,
        "summary": "Specializing in distributed systems and cloud APIs.",
        "education": ["B.S. in Computer Science"],
    }

    text = service.build_candidate_embedding_text(candidate_data)
    assert "Title: Lead Software Architect" in text
    assert "Skills: Python, FastAPI, MongoDB" in text
    assert "Experience: 8.0 years" in text
    assert "Summary: Specializing in distributed systems and cloud APIs." in text
    assert "Education: B.S. in Computer Science" in text


def test_embedding_service_empty_text_returns_zero_vector() -> None:
    """Verify empty text returns zero vector without model invocation."""
    service = EmbeddingService()
    zero_vec = service.generate_embedding("")
    assert len(zero_vec) == 384
    assert all(x == 0.0 for x in zero_vec)


def test_embedding_service_generation_with_mocked_model() -> None:
    """Verify generate_embedding calls underlying model and produces normalized float list."""
    service = EmbeddingService()
    mock_model = MagicMock()
    mock_vector = MagicMock()
    mock_vector.tolist.return_value = [0.05] * 384
    mock_model.encode.return_value = mock_vector
    mock_model.get_sentence_embedding_dimension.return_value = 384

    service._model = mock_model
    vector = service.generate_embedding("Python FastAPI Developer")

    assert len(vector) == 384
    assert vector[0] == 0.05
    mock_model.encode.assert_called_once_with("Python FastAPI Developer", normalize_embeddings=True)


def test_embedding_service_batch_generation() -> None:
    """Verify generate_embeddings encodes multiple texts."""
    service = EmbeddingService()
    mock_model = MagicMock()
    v1 = MagicMock()
    v1.tolist.return_value = [0.1] * 384
    v2 = MagicMock()
    v2.tolist.return_value = [0.2] * 384
    mock_model.encode.return_value = [v1, v2]

    service._model = mock_model
    results = service.generate_embeddings(["Text one", "Text two"])

    assert len(results) == 2
    assert len(results[0]) == 384
    assert len(results[1]) == 384
