from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class UploadModel(BaseModel):
    """Document schema for tracking uploaded resumes in MongoDB."""

    id: Optional[str] = Field(default=None, alias="_id")
    filename: str
    file_size: int
    content_type: str = "application/pdf"
    storage_provider: Optional[str] = None
    bucket_name: Optional[str] = None
    object_name: Optional[str] = None
    storage_status: Optional[str] = None
    user_id: Optional[str] = "test_user"
    page_count: int
    char_count: int
    status: str = "extracted"  # "extracted" | "failed" | "parsed"
    raw_text: str
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "filename": "john_doe_resume.pdf",
                "file_size": 154200,
                "content_type": "application/pdf",
                "storage_provider": "oracle_object_storage",
                "bucket_name": "resume_bucket",
                "object_name": "resumes/2026/10/uuid.pdf",
                "storage_status": "uploaded",
                "user_id": "60c72b2f9b1d8b2bad000001",
                "page_count": 2,
                "char_count": 3450,
                "status": "extracted",
            }
        },
    )

    def to_mongo(self) -> Dict[str, Any]:
        """Convert model to MongoDB document dict, excluding None _id."""
        doc = self.model_dump(by_alias=True, exclude_none=True)
        from bson import ObjectId
        if "_id" in doc and isinstance(doc["_id"], str) and ObjectId.is_valid(doc["_id"]):
            doc["_id"] = ObjectId(doc["_id"])
        return doc
