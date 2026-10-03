from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserModel(BaseModel):
    """Internal MongoDB User document model."""

    id: Optional[str] = Field(default=None, alias="_id")
    email: EmailStr
    full_name: str
    hashed_password: str
    role: str = "recruiter"  # "recruiter" | "admin"
    profile_picture: Optional[str] = Field(default=None, description="URL or base64 profile picture")
    company_name: Optional[str] = Field(default=None, description="Associated organization or company name")
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "email": "recruiter@example.com",
                "full_name": "Jane Doe",
                "role": "recruiter",
                "profile_picture": "https://example.com/profiles/jane.jpg",
                "company_name": "Tech Corp",
                "is_active": True,
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
