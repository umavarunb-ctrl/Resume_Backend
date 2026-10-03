from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from pymongo.collection import Collection
from pymongo.database import Database

from app.models.user import UserModel


class UserRepository:
    """Repository handling database operations for the users collection."""

    def __init__(self, db: Database) -> None:
        self.collection: Collection = db["users"]

    def ensure_indexes(self) -> None:
        """Create unique index on email."""
        self.collection.create_index("email", unique=True)

    def find_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Retrieve user document by lowercase email."""
        return self.collection.find_one({"email": email.lower().strip()})

    def find_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve user document by string or ObjectId."""
        try:
            query_id = ObjectId(user_id) if ObjectId.is_valid(user_id) else user_id
            return self.collection.find_one({"_id": query_id})
        except Exception:
            return None

    def create(self, user: UserModel) -> Dict[str, Any]:
        """Insert a new user document into MongoDB."""
        doc = user.to_mongo()
        doc["email"] = doc["email"].lower().strip()
        result = self.collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    def update_timestamp(self, user_id: str) -> None:
        """Update updated_at timestamp."""
        try:
            query_id = ObjectId(user_id) if ObjectId.is_valid(user_id) else user_id
            self.collection.update_one(
                {"_id": query_id},
                {"$set": {"updated_at": datetime.now(timezone.utc)}},
            )
        except Exception:
            pass

    def update_user(self, user_id: str, update_fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update user document fields and return the updated document."""
        try:
            query_id = ObjectId(user_id) if ObjectId.is_valid(user_id) else user_id
            update_fields["updated_at"] = datetime.now(timezone.utc)
            self.collection.update_one(
                {"_id": query_id},
                {"$set": update_fields},
            )
            return self.find_by_id(user_id)
        except Exception:
            return None

    def list_users(self, skip: int = 0, limit: int = 10) -> Tuple[List[Dict[str, Any]], int]:
        """List paginated users and total count."""
        total = self.collection.count_documents({})
        cursor = self.collection.find().skip(skip).limit(limit).sort("created_at", -1)
        return list(cursor), total

    def search_internal_users(self, query: str, allowed_roles: List[str], limit: int = 20) -> List[Dict[str, Any]]:
        """Search for internal users by name or email."""
        regex_query = {"$regex": query, "$options": "i"}
        cursor = self.collection.find({
            "is_active": True,
            "role": {"$in": allowed_roles},
            "$or": [
                {"full_name": regex_query},
                {"email": regex_query}
            ]
        }).limit(limit).sort("full_name", 1)
        return list(cursor)
