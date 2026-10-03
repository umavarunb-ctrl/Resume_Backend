from typing import Optional
from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.models.upload import UploadModel
from app.repositories.upload_repository import UploadRepository
from app.schemas.upload import (
    UploadDetailResponse,
    UploadListResponse,
    UploadResponse,
)
from app.services.pdf_service import PDFService
from app.services.storage_service import StorageService
from bson import ObjectId


class ResumeService:
    """Service orchestrating resume uploads, validation, text extraction, and tracking."""

    def __init__(
        self,
        upload_repo: UploadRepository,
        pdf_service: PDFService,
        storage_service: StorageService,
    ) -> None:
        self.upload_repo = upload_repo
        self.pdf_service = pdf_service
        self.storage_service = storage_service

    async def process_resume_upload(
        self,
        file: UploadFile,
        current_user_id: Optional[str] = "test_user",
    ) -> UploadResponse:
        """Validate, extract selectable text from PDF, and record upload metadata."""
        filename = file.filename or "resume.pdf"
        if not filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF documents (.pdf) are supported.",
            )

        allowed_content_types = {"application/pdf", "application/x-pdf", "binary/octet-stream"}
        if file.content_type and file.content_type.lower() not in allowed_content_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file content type '{file.content_type}'. Must be application/pdf.",
            )

        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        file_bytes = bytearray()

        # Stream file in chunks to enforce size constraint safely
        while chunk := await file.read(64 * 1024):
            file_bytes.extend(chunk)
            if len(file_bytes) > max_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Uploaded file exceeds the maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB.",
                )

        if len(file_bytes) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        resume_id = str(ObjectId())
        object_name = None
        
        if self.storage_service.enabled:
            object_name = self.storage_service.generate_object_name(filename, resume_id)
            self.storage_service.upload_file(bytes(file_bytes), object_name, content_type="application/pdf")

        try:
            extracted_text, page_count = self.pdf_service.extract_text_from_bytes(bytes(file_bytes))
        except Exception as e:
            if self.storage_service.enabled and object_name:
                self.storage_service.delete_file(object_name)
            raise e

        upload_model = UploadModel(
            id=resume_id,
            filename=filename,
            file_size=len(file_bytes),
            content_type="application/pdf",
            storage_provider="oracle_object_storage" if self.storage_service.enabled else None,
            bucket_name=self.storage_service.bucket_name if self.storage_service.enabled else None,
            object_name=object_name,
            storage_status="uploaded" if self.storage_service.enabled else None,
            user_id=current_user_id or "test_user",
            page_count=page_count,
            char_count=len(extracted_text),
            status="extracted",
            raw_text=extracted_text,
        )

        try:
            saved_doc = self.upload_repo.create(upload_model)
        except Exception as e:
            if self.storage_service.enabled and object_name:
                self.storage_service.delete_file(object_name)
            raise e

        return UploadResponse(
            file_id=str(saved_doc["_id"]),
            filename=saved_doc["filename"],
            file_size=saved_doc["file_size"],
            page_count=saved_doc["page_count"],
            char_count=saved_doc["char_count"],
            status=saved_doc["status"],
            text_preview=saved_doc["raw_text"][:300].strip(),
            created_at=saved_doc["created_at"],
        )

    def get_upload_detail(
        self,
        upload_id: str,
        current_user_id: Optional[str] = None,
    ) -> UploadDetailResponse:
        """Fetch complete upload details including full extracted text."""
        doc = self.upload_repo.find_by_id(upload_id)
        if doc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume upload not found.",
            )
        if current_user_id is not None and doc.get("user_id") != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume upload not found.",
            )

        return UploadDetailResponse(
            file_id=str(doc["_id"]),
            filename=doc["filename"],
            file_size=doc["file_size"],
            page_count=doc["page_count"],
            char_count=doc["char_count"],
            status=doc["status"],
            raw_text=doc["raw_text"],
            created_at=doc["created_at"],
        )

    def list_user_uploads(
        self,
        user_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
    ) -> UploadListResponse:
        """List paginated uploads."""
        skip = (page - 1) * page_size
        items_docs, total = self.upload_repo.find_by_user(user_id=user_id, skip=skip, limit=page_size)

        items = [
            UploadResponse(
                file_id=str(doc["_id"]),
                filename=doc["filename"],
                file_size=doc["file_size"],
                page_count=doc["page_count"],
                char_count=doc["char_count"],
                status=doc["status"],
                text_preview=doc["raw_text"][:300].strip(),
                created_at=doc["created_at"],
            )
            for doc in items_docs
        ]

        return UploadListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_resume_download_url(self, file_id: str, current_user_id: Optional[str] = None) -> str:
        """Get a Pre-Authenticated Request URL to download the resume."""
        doc = self.upload_repo.find_by_id(file_id)
        if doc is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume upload not found.")
        if current_user_id is not None and doc.get("user_id") != current_user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume upload not found.")
        
        object_name = doc.get("object_name")
        if not object_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Resume PDF was not stored in Object Storage.")
            
        return self.storage_service.generate_presigned_url(object_name)

    def delete_resume(self, file_id: str, current_user_id: Optional[str] = None) -> None:
        """Delete a resume upload and its corresponding object in storage."""
        doc = self.upload_repo.find_by_id(file_id)
        if doc is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume upload not found.")
        if current_user_id is not None and doc.get("user_id") != current_user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume upload not found.")
            
        # Delete from OCI if exists
        object_name = doc.get("object_name")
        if object_name and self.storage_service.enabled:
            self.storage_service.delete_file(object_name)
            
        # Delete from MongoDB
        self.upload_repo.delete(file_id)
