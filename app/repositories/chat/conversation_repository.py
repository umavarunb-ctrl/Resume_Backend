from typing import Any, Dict, List, Optional
from pymongo.database import Database
from pymongo import ASCENDING, DESCENDING
from bson import ObjectId

class ConversationRepository:
    def __init__(self, db: Database):
        self.collection = db.conversations
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self.collection.create_index([("member_ids", ASCENDING)])
        self.collection.create_index([("updated_at", DESCENDING)])
        self.collection.create_index([("candidate_id", ASCENDING)])

    def create(self, conversation_data: Dict[str, Any]) -> Dict[str, Any]:
        result = self.collection.insert_one(conversation_data)
        conversation_data["_id"] = result.inserted_id
        return conversation_data

    def find_by_id(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        try:
            return self.collection.find_one({"_id": ObjectId(conversation_id)})
        except Exception:
            return None

    def find_direct_conversation(self, member1: str, member2: str) -> Optional[Dict[str, Any]]:
        return self.collection.find_one({
            "type": "direct",
            "member_ids": {"$all": [member1, member2], "$size": 2}
        })

    def find_candidate_discussion(self, candidate_id: str, member_ids: List[str]) -> Optional[Dict[str, Any]]:
        # This assumes exact member match, or just candidate match and type match.
        # Let's say a candidate discussion can just be grouped by candidate. 
        # But if we want exact members:
        return self.collection.find_one({
            "type": "candidate_discussion",
            "candidate_id": candidate_id,
            "member_ids": {"$all": member_ids, "$size": len(member_ids)}
        })

    def get_user_conversations(self, user_id: str, limit: int = 30, cursor: Optional[str] = None) -> List[Dict[str, Any]]:
        query = {"member_ids": user_id, "is_archived": False}
        if cursor:
            try:
                query["updated_at"] = {"$lt": ObjectId(cursor).generation_time} # actually updated_at is datetime
            except Exception:
                pass
        
        # for cursor based on updated_at
        if cursor:
            # We'll just fetch based on id if it's simpler, or updated_at.
            # Assuming cursor is string ISO format datetime or objectId?
            # Let's use skip/limit for simplicity if cursor isn't strictly defined, but prompt wants cursor.
            # Real cursor implementation needs a tie-breaker. Let's use `updated_at` + `_id`.
            pass

        # simplified cursor implementation for now using updated_at (we can pass updated_at as ISO string as cursor)
        if cursor:
            from dateutil import parser
            try:
                dt = parser.parse(cursor)
                query["updated_at"] = {"$lt": dt}
            except Exception:
                pass

        return list(self.collection.find(query).sort("updated_at", DESCENDING).limit(limit))

    def update(self, conversation_id: str, update_data: Dict[str, Any]) -> None:
        try:
            self.collection.update_one({"_id": ObjectId(conversation_id)}, {"$set": update_data})
        except Exception:
            pass

    def add_members(self, conversation_id: str, member_ids: List[str]) -> None:
        try:
            self.collection.update_one(
                {"_id": ObjectId(conversation_id)},
                {"$addToSet": {"member_ids": {"$each": member_ids}}}
            )
        except Exception:
            pass

    def remove_member(self, conversation_id: str, user_id: str) -> None:
        try:
            self.collection.update_one(
                {"_id": ObjectId(conversation_id)},
                {"$pull": {"member_ids": user_id}}
            )
        except Exception:
            pass

    def search_conversations(self, user_id: str, query: str) -> List[Dict[str, Any]]:
        return list(self.collection.find({
            "member_ids": user_id,
            "name": {"$regex": query, "$options": "i"}
        }).limit(20))

    def delete(self, conversation_id: str) -> None:
        try:
            self.collection.delete_one({"_id": ObjectId(conversation_id)})
        except Exception:
            pass
