import math
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status

from app.core.logging import logger
from app.models.candidate import CandidateModel
from app.repositories.candidate_repository import CandidateRepository
from app.repositories.upload_repository import UploadRepository
from app.schemas.candidate import (
    CandidateCreateRequest,
    CandidateListResponse,
    CandidateResponse,
)
from app.services.embedding_service import EmbeddingService
from app.services.parsing_service import ParsingService


class CandidateService:
    """Service orchestrating candidate parsing, profile assembly, and database storage."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        upload_repo: UploadRepository,
        parsing_service: ParsingService,
        embedding_service: Optional[EmbeddingService] = None,
    ) -> None:
        self.candidate_repo = candidate_repo
        self.upload_repo = upload_repo
        self.parsing_service = parsing_service
        self.embedding_service = embedding_service

    def _to_response(self, doc: Dict[str, Any]) -> CandidateResponse:
        """Map MongoDB document to Pydantic CandidateResponse."""
        raw_edu = doc.get("education", [])
        formatted_edu = []
        for e in raw_edu:
            if isinstance(e, str):
                formatted_edu.append({"degree": e})
            else:
                formatted_edu.append(e)

        return CandidateResponse(
            id=str(doc["_id"]),
            upload_id=str(doc.get("upload_id")) if doc.get("upload_id") else None,
            full_name=doc.get("full_name", "Unknown Candidate"),
            email=doc.get("email"),
            phone=doc.get("phone"),
            title=doc.get("title"),
            skills=doc.get("skills", []),
            experience_years=doc.get("experience_years"),
            education=formatted_edu,
            certifications=doc.get("certifications", []),
            experiences=doc.get("experiences", []),
            summary=doc.get("summary"),
            created_at=doc.get("created_at"),
        )

    def parse_and_create_from_upload(self, upload_id: str) -> CandidateResponse:
        """Parse resume text from an existing upload record into a structured candidate profile."""
        upload_doc = self.upload_repo.find_by_id(upload_id)
        if upload_doc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume upload not found.",
            )

        # Check if already parsed
        existing = self.candidate_repo.find_by_upload_id(upload_id)
        if existing is not None:
            return self._to_response(existing)

        raw_text = upload_doc.get("raw_text", "")
        if not raw_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Upload record contains no extracted text to parse.",
            )

        parsed_fields = self.parsing_service.parse_resume_text(raw_text)

        # Generate dense semantic vector embedding
        embedding = None
        if self.embedding_service:
            try:
                emb_text = self.embedding_service.build_candidate_embedding_text(parsed_fields)
                embedding = self.embedding_service.generate_embedding(emb_text)
            except Exception as e:
                logger.warning("Failed to compute embedding for candidate: %s", e)

        candidate = CandidateModel(
            upload_id=upload_id,
            full_name=parsed_fields["full_name"],
            email=parsed_fields["email"],
            phone=parsed_fields["phone"],
            title=parsed_fields["title"],
            skills=parsed_fields["skills"],
            experience_years=parsed_fields["experience_years"],
            education=parsed_fields["education"],
            certifications=parsed_fields.get("certifications", []),
            experiences=parsed_fields.get("experiences", []),
            summary=parsed_fields["summary"],
            embedding=embedding,
            raw_text=raw_text,
        )

        saved_doc = self.candidate_repo.create(candidate)
        return self._to_response(saved_doc)

    def create_candidate(self, payload: CandidateCreateRequest) -> CandidateResponse:
        """Directly create candidate profile without upload."""
        candidate_dict = payload.model_dump()
        embedding = None
        if self.embedding_service:
            try:
                emb_text = self.embedding_service.build_candidate_embedding_text(candidate_dict)
                embedding = self.embedding_service.generate_embedding(emb_text)
            except Exception as e:
                logger.warning("Failed to compute embedding for candidate: %s", e)

        candidate = CandidateModel(
            full_name=payload.full_name,
            email=payload.email,
            phone=payload.phone,
            title=payload.title,
            skills=payload.skills,
            experience_years=payload.experience_years,
            education=payload.education,
            certifications=payload.certifications,
            experiences=payload.experiences,
            summary=payload.summary,
            embedding=embedding,
        )
        saved_doc = self.candidate_repo.create(candidate)
        return self._to_response(saved_doc)

    def get_candidate(self, candidate_id: str) -> CandidateResponse:
        """Retrieve candidate profile by ID."""
        doc = self.candidate_repo.find_by_id(candidate_id)
        if doc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Candidate not found.",
            )
        return self._to_response(doc)

    def list_candidates(
        self,
        skills: Optional[List[str]] = None,
        q: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
    ) -> CandidateListResponse:
        """List candidates with optional skills filter and keyword search."""
        skip = (page - 1) * page_size
        docs, total = self.candidate_repo.list_candidates(
            skills=skills,
            q=q,
            skip=skip,
            limit=page_size,
        )

        total_pages = math.ceil(total / page_size) if total > 0 and page_size > 0 else 0
        has_next = page < total_pages
        has_prev = page > 1 and total > 0

        return CandidateListResponse(
            items=[self._to_response(d) for d in docs],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=has_next,
            has_prev=has_prev,
        )

    def delete_candidate(self, candidate_id: str) -> None:
        """Delete candidate profile by ID."""
        success = self.candidate_repo.delete(candidate_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Candidate not found or already deleted.",
            )
