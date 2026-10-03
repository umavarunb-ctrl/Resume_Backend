from typing import List, Optional
from datetime import datetime, timezone
from fastapi import HTTPException, status

from app.models.chat import MessageModel
from app.repositories.chat.message_repository import MessageRepository
from app.repositories.chat.conversation_repository import ConversationRepository
from app.services.chat.authorization_service import AuthorizationService
from app.services.chat.websocket_manager import ws_manager
from app.schemas.chat import SendMessageRequest, UpdateMessageRequest, ReactionRequest, ShareCandidateRequest

class MessageService:
    def __init__(
        self,
        msg_repo: MessageRepository,
        conv_repo: ConversationRepository,
        auth_service: AuthorizationService
    ):
        self.msg_repo = msg_repo
        self.conv_repo = conv_repo
        self.auth_service = auth_service

    def get_messages(self, conversation_id: str, current_user_id: str, limit: int = 50, cursor: Optional[str] = None):
        self.auth_service.require_conversation_member(current_user_id, conversation_id)
        
        messages = self.msg_repo.get_conversation_messages(conversation_id, limit + 1, cursor)
        
        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]
            
        next_cursor = None
        if messages:
            next_cursor = str(messages[-1]["_id"])

        for m in messages:
            m["id"] = str(m.pop("_id", m.get("_id")))

        return {
            "messages": messages,
            "has_more": has_more,
            "next_cursor": next_cursor
        }

    async def send_message(self, conversation_id: str, req: SendMessageRequest, current_user_id: str):
        conv = self.auth_service.require_conversation_member(current_user_id, conversation_id)
        
        # Verify reply_to exists in same conversation
        if req.reply_to:
            parent = self.msg_repo.find_by_id(req.reply_to)
            if not parent or parent.get("conversation_id") != conversation_id:
                raise HTTPException(status_code=400, detail="Invalid reply_to message.")
                
        # Filter valid mentions
        valid_mentions = [m for m in req.mentions if m in conv.get("member_ids", [])]

        model = MessageModel(
            conversation_id=conversation_id,
            sender_id=current_user_id,
            type=req.type,
            content=req.content,
            reply_to=req.reply_to,
            attachments=req.attachments,
            candidate_id=req.candidate_id,
            mentions=valid_mentions,
            read_by=[current_user_id]
        )
        
        msg_doc = self.msg_repo.create(model.to_mongo())
        
        # Update conversation updated_at
        self.conv_repo.update(conversation_id, {"updated_at": datetime.now(timezone.utc)})

        msg_doc["id"] = str(msg_doc.pop("_id", msg_doc.get("_id")))
        
        # Broadcast message
        await ws_manager.broadcast_to_room(conversation_id, {
            "event": "message.created",
            "conversation_id": conversation_id,
            "data": {"message": msg_doc}
        })
        
        return msg_doc

    async def update_message(self, message_id: str, req: UpdateMessageRequest, current_user_id: str):
        msg = self.msg_repo.find_by_id(message_id)
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")
            
        if msg.get("sender_id") != current_user_id:
            raise HTTPException(status_code=403, detail="You can only edit your own messages")
            
        update_data = {
            "content": req.content,
            "is_edited": True,
            "updated_at": datetime.now(timezone.utc)
        }
        
        self.msg_repo.update(message_id, update_data)
        msg.update(update_data)
        msg["id"] = str(msg.pop("_id", msg.get("_id")))
        
        await ws_manager.broadcast_to_room(msg["conversation_id"], {
            "event": "message.updated",
            "conversation_id": msg["conversation_id"],
            "data": {"message": msg}
        })
        
        return msg

    async def delete_message(self, message_id: str, current_user_id: str):
        msg = self.msg_repo.find_by_id(message_id)
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")
            
        if msg.get("sender_id") != current_user_id:
            raise HTTPException(status_code=403, detail="You can only delete your own messages")
            
        self.msg_repo.mark_as_deleted(message_id, datetime.now(timezone.utc))
        
        await ws_manager.broadcast_to_room(msg["conversation_id"], {
            "event": "message.deleted",
            "conversation_id": msg["conversation_id"],
            "data": {"message_id": message_id}
        })
        
    async def toggle_reaction(self, message_id: str, req: ReactionRequest, current_user_id: str):
        msg = self.msg_repo.find_by_id(message_id)
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")
            
        conv_id = msg.get("conversation_id")
        self.auth_service.require_conversation_member(current_user_id, conv_id)
        
        reactions = msg.get("reactions", [])
        existing = next((r for r in reactions if r["emoji"] == req.emoji and r["user_id"] == current_user_id), None)
        
        if existing:
            self.msg_repo.remove_reaction(message_id, req.emoji, current_user_id)
            event_type = "reaction.removed"
        else:
            self.msg_repo.add_reaction(message_id, {"emoji": req.emoji, "user_id": current_user_id})
            event_type = "reaction.added"
            
        await ws_manager.broadcast_to_room(conv_id, {
            "event": event_type,
            "conversation_id": conv_id,
            "data": {
                "message_id": message_id,
                "emoji": req.emoji,
                "user_id": current_user_id
            }
        })

    def mark_conversation_read(self, conversation_id: str, current_user_id: str):
        self.auth_service.require_conversation_member(current_user_id, conversation_id)
        self.msg_repo.mark_read(conversation_id, current_user_id)

    async def share_candidate(self, conversation_id: str, req: ShareCandidateRequest, current_user_id: str):
        conv = self.auth_service.require_conversation_member(current_user_id, conversation_id)
        
        # Here we should verify the candidate exists and user has access to it.
        # This can be done via CandidateRepository.
        
        model = MessageModel(
            conversation_id=conversation_id,
            sender_id=current_user_id,
            type="candidate",
            content=req.message or f"Shared candidate {req.candidate_id}",
            candidate_id=req.candidate_id,
            read_by=[current_user_id]
        )
        
        msg_doc = self.msg_repo.create(model.to_mongo())
        self.conv_repo.update(conversation_id, {"updated_at": datetime.now(timezone.utc)})

        msg_doc["id"] = str(msg_doc.pop("_id", msg_doc.get("_id")))
        
        await ws_manager.broadcast_to_room(conversation_id, {
            "event": "message.created",
            "conversation_id": conversation_id,
            "data": {"message": msg_doc}
        })
        
        return msg_doc

    async def toggle_pin(self, message_id: str, is_pinned: bool, current_user_id: str):
        msg = self.msg_repo.find_by_id(message_id)
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")
            
        conv_id = msg.get("conversation_id")
        self.auth_service.require_conversation_member(current_user_id, conv_id)
        
        self.msg_repo.set_pin(message_id, is_pinned)
        
        event_type = "message.pinned" if is_pinned else "message.unpinned"
        await ws_manager.broadcast_to_room(conv_id, {
            "event": event_type,
            "conversation_id": conv_id,
            "data": {"message_id": message_id}
        })
