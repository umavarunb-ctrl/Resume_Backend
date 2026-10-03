from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# -----------------
# Requests
# -----------------
class CreateConversationRequest(BaseModel):
    type: str = Field(..., description="direct | group | candidate_discussion")
    name: Optional[str] = None
    member_ids: List[str] = Field(default_factory=list, min_length=1)
    candidate_id: Optional[str] = None

class UpdateConversationRequest(BaseModel):
    name: Optional[str] = None

class SendMessageRequest(BaseModel):
    content: str = Field(..., max_length=10000)
    type: str = Field(default="text")
    reply_to: Optional[str] = None
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    candidate_id: Optional[str] = None
    mentions: List[str] = Field(default_factory=list)

class UpdateMessageRequest(BaseModel):
    content: str = Field(..., max_length=10000)

class ReactionRequest(BaseModel):
    emoji: str = Field(...)

class ShareCandidateRequest(BaseModel):
    candidate_id: str = Field(...)
    message: Optional[str] = None

class AddMemberRequest(BaseModel):
    member_ids: List[str] = Field(..., min_length=1)

# -----------------
# Responses
# -----------------
class ConversationResponse(BaseModel):
    id: str
    type: str
    name: Optional[str] = None
    member_ids: List[str]
    candidate_id: Optional[str] = None
    created_by: str
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    unread_count: int = 0

class PaginatedConversationsResponse(BaseModel):
    conversations: List[ConversationResponse]
    has_more: bool
    next_cursor: Optional[str] = None

class Reaction(BaseModel):
    emoji: str
    user_id: str

class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    sender_id: str
    type: str
    content: str
    reply_to: Optional[str] = None
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    candidate_id: Optional[str] = None
    mentions: List[str] = Field(default_factory=list)
    reactions: List[Reaction] = Field(default_factory=list)
    is_edited: bool
    is_pinned: bool = False
    is_deleted: bool
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    read_by: List[str] = Field(default_factory=list)

class PaginatedMessagesResponse(BaseModel):
    messages: List[MessageResponse]
    has_more: bool
    next_cursor: Optional[str] = None

class NotificationResponse(BaseModel):
    id: str
    user_id: str
    type: str
    conversation_id: str
    message_id: Optional[str] = None
    actor_id: str
    content: str
    is_read: bool
    created_at: datetime

class PaginatedNotificationsResponse(BaseModel):
    notifications: List[NotificationResponse]
    has_more: bool
    next_cursor: Optional[str] = None
