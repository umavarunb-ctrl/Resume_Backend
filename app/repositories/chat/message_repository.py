from typing import Any, Dict, List, Optional, Tuple
from pymongo.database import Database
from pymongo import ASCENDING, DESCENDING
from bson import ObjectId

class MessageRepository:
    def __init__(self, db: Database):
        self.collection = db.messages
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self.collection.create_index([("conversation_id", ASCENDING), ("created_at", DESCENDING)])
        self.collection.create_index([("sender_id", ASCENDING)])

    def create(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        result = self.collection.insert_one(message_data)
        message_data["_id"] = result.inserted_id
        return message_data

    def find_by_id(self, message_id: str) -> Optional[Dict[str, Any]]:
        try:
            return self.collection.find_one({"_id": ObjectId(message_id)})
        except Exception:
            return None

    def get_conversation_messages(
        self, conversation_id: str, limit: int = 50, cursor: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {"conversation_id": conversation_id}
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

    def update(self, message_id: str, update_data: Dict[str, Any]) -> None:
        try:
            self.collection.update_one({"_id": ObjectId(message_id)}, {"$set": update_data})
        except Exception:
            pass

    def mark_as_deleted(self, message_id: str, deleted_at: Any) -> None:
        try:
            self.collection.update_one(
                {"_id": ObjectId(message_id)}, 
                {"$set": {"is_deleted": True, "deleted_at": deleted_at}}
            )
        except Exception:
            pass

    def add_reaction(self, message_id: str, reaction: Dict[str, Any]) -> None:
        try:
            # We want to remove any existing reaction with same emoji and user_id first, 
            # or we could do it in service layer. Let's do it simply here.
            self.collection.update_one(
                {"_id": ObjectId(message_id)},
                {"$addToSet": {"reactions": reaction}}
            )
        except Exception:
            pass

    def remove_reaction(self, message_id: str, emoji: str, user_id: str) -> None:
        try:
            self.collection.update_one(
                {"_id": ObjectId(message_id)},
                {"$pull": {"reactions": {"emoji": emoji, "user_id": user_id}}}
            )
        except Exception:
            pass

    def set_pin(self, message_id: str, is_pinned: bool) -> None:
        try:
            self.collection.update_one(
                {"_id": ObjectId(message_id)},
                {"$set": {"is_pinned": is_pinned}}
            )
        except Exception:
            pass

    def search_messages(self, conversation_ids: List[str], query: str) -> List[Dict[str, Any]]:
        return list(self.collection.find({
            "conversation_id": {"$in": conversation_ids},
            "content": {"$regex": query, "$options": "i"},
            "is_deleted": False
        }).limit(50))

    def mark_read(self, conversation_id: str, user_id: str) -> None:
        # Mark all messages in conversation as read by this user
        self.collection.update_many(
            {"conversation_id": conversation_id, "read_by": {"$ne": user_id}},
            {"$push": {"read_by": user_id}}
        )

    def count_unread(self, conversation_id: str, user_id: str) -> int:
        return self.collection.count_documents({
            "conversation_id": conversation_id,
            "read_by": {"$ne": user_id}
        })
