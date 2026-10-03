from typing import List, Optional
from fastapi import HTTPException, status
from app.repositories.user_repository import UserRepository
from app.repositories.chat.conversation_repository import ConversationRepository

class AuthorizationService:
    def __init__(self, user_repo: UserRepository, conv_repo: ConversationRepository):
        self.user_repo = user_repo
        self.conv_repo = conv_repo
        self.ALLOWED_CHAT_ROLES = {"recruiter", "senior_recruiter", "hiring_manager", "admin"}

    def require_internal_user(self, user_id: str) -> bool:
        user = self.user_repo.find_by_id(user_id)
        if not user or user.get("role", "recruiter").lower() not in self.ALLOWED_CHAT_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have access to internal chat."
            )
        return True

    def is_internal_user(self, user_id: str) -> bool:
        user = self.user_repo.find_by_id(user_id)
        if user and user.get("role", "recruiter").lower() in self.ALLOWED_CHAT_ROLES:
            return True
        return False

    def is_conversation_member(self, user_id: str, conversation_id: str) -> bool:
        conv = self.conv_repo.find_by_id(conversation_id)
        if not conv:
            return False
        return user_id in conv.get("member_ids", [])

    def require_conversation_member(self, user_id: str, conversation_id: str) -> dict:
        conv = self.conv_repo.find_by_id(conversation_id)
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found."
            )
        if user_id not in conv.get("member_ids", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this conversation."
            )
        return conv

    def filter_valid_internal_users(self, user_ids: List[str]) -> List[str]:
        valid_users = []
        for uid in set(user_ids):
            if self.is_internal_user(uid):
                valid_users.append(uid)
        return valid_users
