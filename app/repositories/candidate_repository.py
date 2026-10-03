import re
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from pymongo.collection import Collection
from pymongo.database import Database

from app.models.candidate import CandidateModel


class CandidateRepository:
    """Repository handling database operations for the candidates collection."""

    def __init__(self, db: Database) -> None:
        self.collection: Collection = db["candidates"]

    def ensure_indexes(self) -> None:
        """Create indexes for skills filtering, upload references, and search."""
        self.collection.create_index("skills")
        self.collection.create_index("upload_id")
        self.collection.create_index("email")
        self.collection.create_index([("created_at", -1)])

    def create(self, candidate: CandidateModel) -> Dict[str, Any]:
        """Insert candidate profile document into MongoDB."""
        doc = candidate.to_mongo()
        result = self.collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    def find_by_id(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve candidate by MongoDB ID."""
        try:
            query_id = ObjectId(candidate_id) if ObjectId.is_valid(candidate_id) else candidate_id
            return self.collection.find_one({"_id": query_id})
        except Exception:
            return None

    def find_by_upload_id(self, upload_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve candidate linked to a specific resume upload."""
        return self.collection.find_one({"upload_id": upload_id})

    def find_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Retrieve candidate by email."""
        return self.collection.find_one({"email": email.lower().strip()})

    def list_candidates(
        self,
        skills: Optional[List[str]] = None,
        q: Optional[str] = None,
        skip: int = 0,
        limit: int = 10,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Query candidates with optional skill filtering and keyword text search.
        """
        query: Dict[str, Any] = {}

        if skills:
            # Match candidates having any/all of the specified skills (case-insensitive)
            regex_skills = [{"skills": {"$regex": f"^{re.escape(s)}$", "$options": "i"}} for s in skills]
            query["$and"] = regex_skills

        if q and q.strip():
            term = q.strip()
            # Search in full_name, title, or summary
            query["$or"] = [
                {"full_name": {"$regex": term, "$options": "i"}},
                {"title": {"$regex": term, "$options": "i"}},
                {"summary": {"$regex": term, "$options": "i"}},
                {"skills": {"$regex": term, "$options": "i"}},
            ]

        cursor = (
            self.collection.find(query)
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        items = list(cursor)
        total = self.collection.count_documents(query)
        return items, total

    def delete(self, candidate_id: str) -> bool:
        """Delete candidate profile by ID."""
        try:
            query_id = ObjectId(candidate_id) if ObjectId.is_valid(candidate_id) else candidate_id
            result = self.collection.delete_one({"_id": query_id})
            return result.deleted_count > 0
        except Exception:
            return False
