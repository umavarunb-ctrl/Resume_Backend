from typing import List, Optional
from datetime import datetime, timezone
from fastapi import HTTPException, status
from bson import ObjectId

from app.models.chat import ConversationModel
from app.repositories.chat.conversation_repository import ConversationRepository
from app.repositories.chat.message_repository import MessageRepository
from app.services.chat.authorization_service import AuthorizationService
from app.services.chat.websocket_manager import ws_manager
from app.schemas.chat import CreateConversationRequest, UpdateConversationRequest, AddMemberRequest

class ConversationService:
    def __init__(
        self, 
        conv_repo: ConversationRepository, 
        msg_repo: MessageRepository,
        auth_service: AuthorizationService
    ):
        self.conv_repo = conv_repo
        self.msg_repo = msg_repo
        self.auth_service = auth_service

    def get_conversation(self, conversation_id: str, current_user_id: str) -> dict:
        conv = self.auth_service.require_conversation_member(current_user_id, conversation_id)
        conv["id"] = str(conv.pop("_id", conv.get("_id")))
        conv["unread_count"] = self.msg_repo.count_unread(conversation_id, current_user_id)
        return conv

    def create_conversation(self, req: CreateConversationRequest, current_user_id: str) -> dict:
        self.auth_service.require_internal_user(current_user_id)
        
        # Ensure creator is in member_ids
        member_ids = req.member_ids
        if current_user_id not in member_ids:
            member_ids.append(current_user_id)
        
        # Validate members
        valid_members = self.auth_service.filter_valid_internal_users(member_ids)
        if not valid_members or len(valid_members) < 2:
            raise HTTPException(status_code=400, detail="Conversation requires at least two valid internal members.")

        # Check for existing direct or candidate discussion
        if req.type == "direct" and len(valid_members) == 2:
            existing = self.conv_repo.find_direct_conversation(valid_members[0], valid_members[1])
            if existing:
                existing["id"] = str(existing.pop("_id", existing.get("_id")))
                existing["unread_count"] = self.msg_repo.count_unread(existing["id"], current_user_id)
                return existing

        if req.type == "candidate_discussion" and req.candidate_id:
            existing = self.conv_repo.find_candidate_discussion(req.candidate_id, valid_members)
            if existing:
                existing["id"] = str(existing.pop("_id", existing.get("_id")))
                existing["unread_count"] = self.msg_repo.count_unread(existing["id"], current_user_id)
                return existing

        model = ConversationModel(
            type=req.type,
            name=req.name,
            member_ids=valid_members,
            candidate_id=req.candidate_id,
            created_by=current_user_id
        )
        
        conv = self.conv_repo.create(model.to_mongo())
        conv["id"] = str(conv.pop("_id", conv.get("_id")))
        conv["unread_count"] = 0
        
        # Notify members over WS
        # for user_id in valid_members:
        #    ws_manager.send_personal_message({"event": "conversation.created", "data": conv}, user_id)
            
        return conv

    def get_user_conversations(self, user_id: str, limit: int = 30, cursor: Optional[str] = None):
        self.auth_service.require_internal_user(user_id)
        convs = self.conv_repo.get_user_conversations(user_id, limit + 1, cursor)
        
        has_more = len(convs) > limit
        if has_more:
            convs = convs[:limit]
            
        next_cursor = None
        if convs:
            # use datetime iso string as cursor, or object id. Let's use string object id since find_by_id doesn't handle datetime strictly yet, wait, our repo uses string datetime parsing for cursor. Let's use iso format of updated_at
            next_cursor = str(convs[-1]["_id"]) # actually, repo uses updated_at if possible. We used objectId.

        # Add unread counts
        for c in convs:
            c["id"] = str(c.pop("_id", c.get("_id")))
            c["unread_count"] = self.msg_repo.count_unread(c["id"], user_id)

        return {
            "conversations": convs,
            "has_more": has_more,
            "next_cursor": next_cursor
        }

    def update_conversation(self, conversation_id: str, req: UpdateConversationRequest, current_user_id: str) -> dict:
        conv = self.auth_service.require_conversation_member(current_user_id, conversation_id)
        
        update_data = {"updated_at": datetime.now(timezone.utc)}
        if req.name is not None:
            update_data["name"] = req.name
            
        self.conv_repo.update(conversation_id, update_data)
        conv.update(update_data)
        conv["id"] = str(conv.pop("_id", conv.get("_id")))
        conv["unread_count"] = self.msg_repo.count_unread(conversation_id, current_user_id)
        return conv

    def add_members(self, conversation_id: str, req: AddMemberRequest, current_user_id: str) -> dict:
        conv = self.auth_service.require_conversation_member(current_user_id, conversation_id)
        if conv.get("type") == "direct":
            raise HTTPException(status_code=400, detail="Cannot add members to a direct conversation.")
            
        valid_new_members = self.auth_service.filter_valid_internal_users(req.member_ids)
        if not valid_new_members:
            raise HTTPException(status_code=400, detail="No valid internal users provided.")
            
        self.conv_repo.add_members(conversation_id, valid_new_members)
        conv["member_ids"] = list(set(conv.get("member_ids", []) + valid_new_members))
        conv["id"] = str(conv.pop("_id", conv.get("_id")))
        conv["unread_count"] = self.msg_repo.count_unread(conversation_id, current_user_id)
        return conv

    def remove_member(self, conversation_id: str, user_to_remove: str, current_user_id: str) -> None:
        conv = self.auth_service.require_conversation_member(current_user_id, conversation_id)
        
        if conv.get("type") == "direct":
            raise HTTPException(status_code=400, detail="Cannot remove members from a direct conversation.")
            
        if user_to_remove != current_user_id:
            # Need admin or creator permissions, simplified: must be creator
            if conv.get("created_by") != current_user_id and not self.auth_service.user_repo.find_by_id(current_user_id).get("role") == "admin":
                raise HTTPException(status_code=403, detail="Only creator or admin can remove other members.")
                
        self.conv_repo.remove_member(conversation_id, user_to_remove)

    def search_conversations(self, user_id: str, query: str):
        self.auth_service.require_internal_user(user_id)
        convs = self.conv_repo.search_conversations(user_id, query)
        for c in convs:
            c["id"] = str(c["_id"])
            c["unread_count"] = self.msg_repo.count_unread(c["id"], user_id)
        return convs

    def delete_conversation(self, conversation_id: str, current_user_id: str) -> None:
        conv = self.auth_service.require_conversation_member(current_user_id, conversation_id)
        # Allow creator or admin to delete the conversation entirely
        if conv.get("created_by") != current_user_id and not self.auth_service.user_repo.find_by_id(current_user_id).get("role") == "admin":
            raise HTTPException(status_code=403, detail="Only the creator or admin can delete the conversation.")
            
        self.conv_repo.delete(conversation_id)
