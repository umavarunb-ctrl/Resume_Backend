from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from pymongo.collection import Collection
from pymongo.database import Database

from app.models.upload import UploadModel


class UploadRepository:
    """Repository handling database operations for the uploads collection."""

    def __init__(self, db: Database) -> None:
        self.collection: Collection = db["uploads"]

    def ensure_indexes(self) -> None:
        """Create indexes for performance."""
        self.collection.create_index([("user_id", 1), ("created_at", -1)])

    def create(self, upload: UploadModel) -> Dict[str, Any]:
        """Insert a new resume upload document into MongoDB."""
        doc = upload.to_mongo()
        result = self.collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    def find_by_id(self, upload_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve upload document by ID."""
        try:
            query_id = ObjectId(upload_id) if ObjectId.is_valid(upload_id) else upload_id
            return self.collection.find_one({"_id": query_id})
        except Exception:
            return None

    def find_by_user(
        self,
        user_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 10,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Retrieve paginated upload documents (filtered by user_id if provided)."""
        query = {"user_id": user_id} if user_id else {}
        cursor = (
            self.collection.find(query)
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        items = list(cursor)
        total = self.collection.count_documents(query)
        return items, total

    def delete(self, upload_id: str) -> bool:
        """Delete an upload document by ID."""
        try:
            query_id = ObjectId(upload_id) if ObjectId.is_valid(upload_id) else upload_id
            result = self.collection.delete_one({"_id": query_id})
            return result.deleted_count > 0
        except Exception:
            return False
