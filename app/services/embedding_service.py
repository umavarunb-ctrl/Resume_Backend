from typing import Any, Dict, List, Optional
from app.core.config import settings
from app.core.logging import logger


class EmbeddingService:
    """
    Vector embedding service using sentence-transformers.
    Produces normalized 384-dimensional dense embeddings for semantic search.
    Loads the underlying neural network lazily on first invocation.
    """

    DEFAULT_DIMENSION = 384

    def __init__(self, model_name: Optional[str] = None) -> None:
        self.model_name = model_name or settings.EMBEDDING_MODEL or "sentence-transformers/all-MiniLM-L6-v2"
        self._model = None
        self.dimension = self.DEFAULT_DIMENSION

    def _get_model(self) -> Any:
        """Lazy loader for SentenceTransformer to optimize memory and startup."""
        if self._model is None:
            logger.info("Initializing SentenceTransformer with model: %s", self.model_name)
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
                # Verify dimension
                self.dimension = self._model.get_sentence_embedding_dimension() or self.DEFAULT_DIMENSION
                logger.info("SentenceTransformer ready. Embedding dimension: %d", self.dimension)
            except Exception as e:
                logger.error("Failed to load SentenceTransformer '%s': %s", self.model_name, e)
                raise RuntimeError(f"Could not initialize embedding model: {e}") from e
        return self._model

    def build_candidate_embedding_text(self, candidate_data: Dict[str, Any]) -> str:
        """
        Synthesize candidate fields into a dense semantic representation.
        Prioritizes title, skills, summary, and experience.
        """
        parts: List[str] = []

        title = candidate_data.get("title")
        if title:
            parts.append(f"Title: {title}")

        skills = candidate_data.get("skills", [])
        if skills:
            parts.append(f"Skills: {', '.join(skills)}")

        exp_years = candidate_data.get("experience_years")
        if exp_years is not None:
            parts.append(f"Experience: {exp_years} years")

        summary = candidate_data.get("summary")
        if summary:
            parts.append(f"Summary: {summary}")

        education = candidate_data.get("education", [])
        if education:
            edu_strs = [e.get("degree") for e in education if isinstance(e, dict) and e.get("degree")]
            if not edu_strs:
                edu_strs = [e for e in education if isinstance(e, str)]
            if edu_strs:
                parts.append(f"Education: {', '.join(edu_strs)}")

        if not parts:
            # Fallback to raw text if structured fields are absent
            raw_text = candidate_data.get("raw_text", "")
            return raw_text[:1000].strip() if raw_text else "Candidate Profile"

        return " | ".join(parts)

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate a normalized 384-dimensional vector embedding for a single text.
        """
        if not text or not text.strip():
            # Return zero vector if text is empty
            return [0.0] * self.dimension

        model = self._get_model()
        vector = model.encode(text.strip(), normalize_embeddings=True)
        return [float(x) for x in vector.tolist()]

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate normalized vector embeddings for a list of texts in batch."""
        if not texts:
            return []

        model = self._get_model()
        cleaned_texts = [t.strip() if t and t.strip() else "" for t in texts]
        vectors = model.encode(cleaned_texts, normalize_embeddings=True)
        return [[float(x) for x in v.tolist()] for v in vectors]
