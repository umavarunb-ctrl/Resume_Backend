from typing import Any, Dict, List, Optional
from pymongo.database import Database
from pymongo import ASCENDING, DESCENDING
from bson import ObjectId

class NotificationRepository:
    def __init__(self, db: Database):
        self.collection = db.notifications
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self.collection.create_index([("user_id", ASCENDING), ("is_read", ASCENDING)])
        self.collection.create_index([("created_at", DESCENDING)])

    def create(self, notification_data: Dict[str, Any]) -> Dict[str, Any]:
        result = self.collection.insert_one(notification_data)
        notification_data["_id"] = result.inserted_id
        return notification_data

    def get_user_notifications(self, user_id: str, limit: int = 50, cursor: Optional[str] = None) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {"user_id": user_id}
        if cursor:
            try:
                query["_id"] = {"$lt": ObjectId(cursor)}
            except Exception:
                pass
                
        return list(
            self.collection.find(query)
            .sort("_id", DESCENDING)
            .limit(limit)
        )

    def mark_read(self, notification_id: str, user_id: str) -> None:
        try:
            self.collection.update_one(
                {"_id": ObjectId(notification_id), "user_id": user_id},
                {"$set": {"is_read": True}}
            )
        except Exception:
            pass

    def mark_all_read(self, user_id: str) -> None:
        self.collection.update_many(
            {"user_id": user_id, "is_read": False},
            {"$set": {"is_read": True}}
        )
