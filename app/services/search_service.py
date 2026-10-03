import re
from typing import Any, Dict, List, Optional, Set
from pymongo.errors import PyMongoError

from app.core.logging import logger
from app.repositories.candidate_repository import CandidateRepository
from app.schemas.candidate import CandidateResponse
from app.schemas.search import (
    HybridSearchRequest,
    SearchCandidateResult,
    SearchFilter,
    SearchResponse,
    SemanticSearchRequest,
)
from app.services.embedding_service import EmbeddingService


# ---------------------------------------------------------------------------
# Education-level keyword mapping
# Each level maps to regex patterns that match common degree abbreviations
# ---------------------------------------------------------------------------
_EDUCATION_PATTERNS: Dict[str, re.Pattern] = {
    "bachelor": re.compile(
        r"\b(?:Bachelor|B\.?S\.?|B\.?A\.?|B\.?Tech|B\.?E\.?|B\.?Sc|B\.?Com|BCA|BBA)\b",
        re.IGNORECASE,
    ),
    "master": re.compile(
        r"\b(?:Master|M\.?S\.?|M\.?A\.?|M\.?Tech|M\.?E\.?|M\.?Sc|M\.?B\.?A\.?|MCA)\b",
        re.IGNORECASE,
    ),
    "phd": re.compile(
        r"\b(?:Ph\.?D\.?|Doctorate|Doctor\s+of)\b",
        re.IGNORECASE,
    ),
}

# Degree hierarchy: PhD > Master > Bachelor
_EDUCATION_RANK = {"bachelor": 1, "master": 2, "phd": 3}


class SearchService:
    """
    Search service integrating MongoDB Atlas Vector Search, semantic embeddings,
    and hybrid attribute/keyword ranking.
    """

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        embedding_service: EmbeddingService,
    ) -> None:
        self.candidate_repo = candidate_repo
        self.embedding_service = embedding_service

    @staticmethod
    def cosine_similarity(v1: List[float], v2: List[float]) -> float:
        """Compute cosine similarity between two normalized float vectors."""
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = sum(a * a for a in v1) ** 0.5
        norm2 = sum(b * b for b in v2) ** 0.5
        if norm1 == 0 or norm2 == 0:
            return 0.0
        sim = dot / (norm1 * norm2)
        return max(0.0, min(1.0, float(sim)))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _to_candidate_response(self, doc: Dict[str, Any]) -> CandidateResponse:
        """Helper mapping MongoDB document to CandidateResponse."""
        raw_edu = doc.get("education", [])
        norm_edu = [{"degree": e} if isinstance(e, str) else e for e in raw_edu]

        raw_certs = doc.get("certifications", [])
        norm_certs = [{"name": c} if isinstance(c, str) else c for c in raw_certs]

        raw_exps = doc.get("experiences", [])

        return CandidateResponse(
            id=str(doc["_id"]),
            upload_id=str(doc.get("upload_id")) if doc.get("upload_id") else None,
            full_name=doc.get("full_name", "Unknown Candidate"),
            email=doc.get("email"),
            phone=doc.get("phone"),
            title=doc.get("title"),
            skills=doc.get("skills", []),
            experience_years=doc.get("experience_years"),
            education=norm_edu,
            certifications=norm_certs,
            experiences=raw_exps,
            summary=doc.get("summary"),
            created_at=doc.get("created_at"),
        )

    @staticmethod
    def _candidate_matches_education(doc: Dict[str, Any], education_filter: str) -> bool:
        """
        Check whether a candidate document satisfies the education level filter.
        A PhD holder also qualifies for a 'master' or 'bachelor' filter (degree hierarchy).
        """
        required_level = education_filter.lower().strip()
        pattern = _EDUCATION_PATTERNS.get(required_level)
        if not pattern:
            return True  # unknown level → no filtering

        required_rank = _EDUCATION_RANK.get(required_level, 0)

        edu_list = doc.get("education", [])
        for edu in edu_list:
            degree_str = edu.get("degree", "") if isinstance(edu, dict) else str(edu)
            if not degree_str:
                continue
            # Check against each level to find the candidate's highest degree
            for level_key, level_pattern in _EDUCATION_PATTERNS.items():
                if level_pattern.search(degree_str):
                    candidate_rank = _EDUCATION_RANK.get(level_key, 0)
                    if candidate_rank >= required_rank:
                        return True
        return False

    @staticmethod
    def _candidate_matches_location(doc: Dict[str, Any], location_filter: str) -> bool:
        """
        Check whether a candidate document matches the location filter.
        Searches across raw_text, experience descriptions, education places,
        and the summary field for flexible location matching.
        """
        loc = location_filter.strip()
        if not loc:
            return True

        # Build a case-insensitive pattern that handles common suffixes and word boundaries
        loc_pattern = re.compile(rf"\b{re.escape(loc)}\b", re.IGNORECASE)

        # 1. Check raw_text (most comprehensive source)
        raw_text = doc.get("raw_text", "")
        if raw_text and loc_pattern.search(raw_text):
            return True

        # 2. Check summary
        summary = doc.get("summary", "")
        if summary and loc_pattern.search(summary):
            return True

        # 3. Check experience entries for location mentions
        for exp in doc.get("experiences", []):
            if isinstance(exp, dict):
                for field in ("description", "company", "title"):
                    val = exp.get(field, "")
                    if val and loc_pattern.search(val):
                        return True

        # 4. Check education entries for place/college location mentions
        for edu in doc.get("education", []):
            if isinstance(edu, dict):
                for field in ("place", "college", "degree"):
                    val = edu.get(field, "")
                    if val and loc_pattern.search(val):
                        return True

        # 5. Check title field
        title = doc.get("title", "")
        if title and loc_pattern.search(title):
            return True

        return False

    @staticmethod
    def _compute_title_match_score(doc: Dict[str, Any], title_filter: str) -> float:
        """
        Compute a fuzzy title match score between 0 and 1.
        Uses token overlap so "Java Developer" matches "Senior Java Developer" partially.
        """
        candidate_title = (doc.get("title") or "").lower()
        if not candidate_title:
            return 0.0

        filter_tokens = set(re.findall(r"\b[a-zA-Z]+\b", title_filter.lower()))
        title_tokens = set(re.findall(r"\b[a-zA-Z]+\b", candidate_title))

        if not filter_tokens:
            return 0.0

        overlap = filter_tokens & title_tokens
        return len(overlap) / len(filter_tokens)

    # ------------------------------------------------------------------
    # Semantic search
    # ------------------------------------------------------------------

    def semantic_search(self, request: SemanticSearchRequest) -> SearchResponse:
        """
        Execute semantic vector search.
        Attempts native MongoDB Atlas $vectorSearch pipeline first.
        Gracefully falls back to vectorized cosine scoring if index is pending on Atlas.
        """
        query_vector = self.embedding_service.generate_embedding(request.query)

        # 1. Attempt Atlas $vectorSearch aggregation stage
        try:
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "vector_index",
                        "path": "embedding",
                        "queryVector": query_vector,
                        "numCandidates": request.limit * 5,
                        "limit": request.limit,
                    }
                },
                {
                    "$project": {
                        "_id": 1,
                        "upload_id": 1,
                        "full_name": 1,
                        "email": 1,
                        "phone": 1,
                        "title": 1,
                        "skills": 1,
                        "experience_years": 1,
                        "education": 1,
                        "certifications": 1,
                        "experiences": 1,
                        "summary": 1,
                        "created_at": 1,
                        "score": {"$meta": "vectorSearchScore"},
                    }
                },
            ]
            cursor = self.candidate_repo.collection.aggregate(pipeline)
            raw_results = list(cursor)

            results: List[SearchCandidateResult] = []
            for doc in raw_results:
                score = float(doc.get("score", 0.0))
                if score >= request.min_score:
                    results.append(
                        SearchCandidateResult(
                            candidate=self._to_candidate_response(doc),
                            score=round(score, 4),
                            match_type="semantic",
                        )
                    )

            if results:
                return SearchResponse(
                    query=request.query,
                    total_matches=len(results),
                    search_type="semantic",
                    results=results,
                )
        except PyMongoError as err:
            logger.info(
                "Atlas $vectorSearch not available or index not yet built (%s). Falling back to direct vector similarity.",
                type(err).__name__,
            )

        # 2. Fallback: Exact Cosine Similarity over candidates in collection
        cursor = self.candidate_repo.collection.find(
            {"embedding": {"$exists": True, "$ne": None}},
            {"raw_text": 0},
        )
        scored_candidates: List[tuple[Dict[str, Any], float]] = []

        for doc in cursor:
            candidate_vec = doc.get("embedding")
            if candidate_vec and isinstance(candidate_vec, list):
                score = self.cosine_similarity(query_vector, candidate_vec)
                if score >= request.min_score:
                    scored_candidates.append((doc, score))

        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        top_candidates = scored_candidates[: request.limit]

        results = [
            SearchCandidateResult(
                candidate=self._to_candidate_response(doc),
                score=round(score, 4),
                match_type="semantic",
            )
            for doc, score in top_candidates
        ]

        return SearchResponse(
            query=request.query,
            total_matches=len(results),
            search_type="semantic",
            results=results,
        )

    # ------------------------------------------------------------------
    # Hybrid search (main enterprise search engine)
    # ------------------------------------------------------------------

    def hybrid_search(self, request: HybridSearchRequest) -> SearchResponse:
        """
        Execute hybrid search combining semantic vector search and enterprise attribute filters.

        Scoring model (weighted sum):
          - Vector similarity  × vector_weight
          - Skill overlap      × 0.5 × (1 - vector_weight)
          - Title match        × 0.3 × (1 - vector_weight)
          - Education bonus    × 0.1 × (1 - vector_weight)
          - Location bonus     × 0.1 × (1 - vector_weight)

        Hard filters (applied via MongoDB query before scoring):
          - experience_years range
          - skills (all / any mode)
          - title (regex)

        Post-query filters (applied in Python for flexible matching):
          - education level (uses degree hierarchy: PhD > Master > Bachelor)
          - location (fuzzy text search across raw_text and structured fields)
        """
        query_vector = self.embedding_service.generate_embedding(request.query)

        # Build MongoDB query for enterprise filters
        filter_conditions: List[Dict[str, Any]] = []
        filters: Optional[SearchFilter] = request.filters

        if filters:
            # 1. Enterprise Experience Filter Logic
            min_exp = filters.min_experience_years
            max_exp = filters.max_experience_years

            if min_exp is not None or max_exp is not None:
                exp_query_parts: List[Dict[str, Any]] = []

                # Numeric range bounds
                num_range: Dict[str, Any] = {}
                if min_exp is not None and min_exp > 0:
                    num_range["$gte"] = min_exp
                if max_exp is not None:
                    num_range["$lte"] = max_exp

                if num_range:
                    exp_query_parts.append({"experience_years": num_range})
                elif min_exp == 0 and max_exp is None:
                    exp_query_parts.append({"experience_years": {"$gte": 0}})

                # If min_exp is None or 0, also preserve candidates with null/missing experience
                if min_exp is None or min_exp == 0:
                    exp_query_parts.append({"experience_years": None})
                    exp_query_parts.append({"experience_years": {"$exists": False}})

                if len(exp_query_parts) == 1:
                    filter_conditions.append(exp_query_parts[0])
                elif len(exp_query_parts) > 1:
                    filter_conditions.append({"$or": exp_query_parts})

            # 2. Skill Filter Logic (ALL vs ANY matching modes)
            if filters.skills:
                clean_skills = [s.strip() for s in filters.skills if s and s.strip()]
                if clean_skills:
                    regex_skills = [{"skills": {"$regex": f"^{re.escape(s)}$", "$options": "i"}} for s in clean_skills]
                    mode = getattr(filters, "skill_match_mode", "all").lower()
                    if mode == "any":
                        filter_conditions.append({"$or": regex_skills})
                    else:
                        filter_conditions.append({"$and": regex_skills})

            # 3. Title / Job Role Filter Logic (fuzzy regex)
            if filters.title and filters.title.strip():
                title_terms = filters.title.strip().split()
                # Build a regex that matches all tokens in any order for flexible matching
                title_regex_parts = [rf"(?=.*\b{re.escape(t)})" for t in title_terms]
                title_regex = "".join(title_regex_parts) + ".*"
                filter_conditions.append({"title": {"$regex": title_regex, "$options": "i"}})

        if filter_conditions:
            if len(filter_conditions) == 1:
                mongo_filter = filter_conditions[0]
            else:
                mongo_filter = {"$and": filter_conditions}
        else:
            mongo_filter = {}

        # Include raw_text in projection for post-query location/education filtering
        candidates_cursor = self.candidate_repo.collection.find(mongo_filter)
        candidates = list(candidates_cursor)

        # Extract search query tokens for keyword match scoring
        query_tokens: Set[str] = set(re.findall(r"\b[a-zA-Z]{3,}\b", request.query.lower()))

        scored_results: List[SearchCandidateResult] = []
        keyword_weight = 1.0 - request.vector_weight

        for doc in candidates:
            # ---------------------------------------------------------------
            # Post-query filters (education & location)
            # ---------------------------------------------------------------
            if filters and filters.education and filters.education.lower() != "any":
                if not self._candidate_matches_education(doc, filters.education):
                    continue

            if filters and filters.location and filters.location.strip():
                if not self._candidate_matches_location(doc, filters.location):
                    continue

            # ---------------------------------------------------------------
            # 1. Semantic Vector Score
            # ---------------------------------------------------------------
            candidate_vec = doc.get("embedding")
            if candidate_vec and isinstance(candidate_vec, list):
                vec_score = self.cosine_similarity(query_vector, candidate_vec)
            else:
                vec_score = 0.0

            # ---------------------------------------------------------------
            # 2. Keyword & Skill Overlap Score
            # ---------------------------------------------------------------
            cand_skills: List[str] = doc.get("skills", [])
            matched_skills: List[str] = []

            for s in cand_skills:
                if s.lower() in query_tokens or (filters and filters.skills and any(s.lower() == req_s.lower() for req_s in filters.skills)):
                    matched_skills.append(s)

            # Keyword match ratio
            kw_match_count = len(matched_skills)
            total_target_kw = max(1, len(filters.skills) if (filters and filters.skills) else len(query_tokens))
            skill_score = min(1.0, kw_match_count / total_target_kw)

            # ---------------------------------------------------------------
            # 3. Title Match Score (fuzzy token overlap)
            # ---------------------------------------------------------------
            title_score = 0.0
            if filters and filters.title and filters.title.strip():
                title_score = self._compute_title_match_score(doc, filters.title)
            elif query_tokens:
                # Even without an explicit title filter, boost candidates whose title
                # overlaps with the natural language query
                candidate_title = (doc.get("title") or "").lower()
                if candidate_title:
                    title_tokens = set(re.findall(r"\b[a-zA-Z]+\b", candidate_title))
                    overlap = query_tokens & title_tokens
                    if overlap:
                        title_score = len(overlap) / max(1, len(query_tokens))

            # ---------------------------------------------------------------
            # 4. Education Bonus
            # ---------------------------------------------------------------
            edu_bonus = 0.0
            if filters and filters.education and filters.education.lower() != "any":
                if self._candidate_matches_education(doc, filters.education):
                    edu_bonus = 1.0

            # ---------------------------------------------------------------
            # 5. Location Bonus
            # ---------------------------------------------------------------
            loc_bonus = 0.0
            if filters and filters.location and filters.location.strip():
                if self._candidate_matches_location(doc, filters.location):
                    loc_bonus = 1.0

            # ---------------------------------------------------------------
            # 6. Weighted Combined Score
            # ---------------------------------------------------------------
            combined_score = (
                (vec_score * request.vector_weight)
                + (skill_score * 0.5 * keyword_weight)
                + (title_score * 0.3 * keyword_weight)
                + (edu_bonus * 0.1 * keyword_weight)
                + (loc_bonus * 0.1 * keyword_weight)
            )

            if combined_score >= request.min_score:
                scored_results.append(
                    SearchCandidateResult(
                        candidate=self._to_candidate_response(doc),
                        score=round(combined_score, 4),
                        matched_skills=matched_skills,
                        match_type="hybrid",
                    )
                )

        scored_results.sort(key=lambda r: r.score, reverse=True)
        top_results = scored_results[: request.limit]

        return SearchResponse(
            query=request.query,
            total_matches=len(top_results),
            search_type="hybrid",
            results=top_results,
        )
