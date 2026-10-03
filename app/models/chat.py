from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

class ConversationModel(BaseModel):
    """Internal MongoDB Conversation document model."""
    id: Optional[str] = Field(default=None, alias="_id")
    type: str = Field(..., description="direct | group | candidate_discussion")
    name: Optional[str] = None
    member_ids: List[str] = Field(default_factory=list)
    candidate_id: Optional[str] = None
    created_by: str
    is_archived: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(populate_by_name=True)

    def to_mongo(self) -> Dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)

class MessageModel(BaseModel):
    """Internal MongoDB Message document model."""
    id: Optional[str] = Field(default=None, alias="_id")
    conversation_id: str
    sender_id: str
    type: str = Field(default="text", description="text | file | candidate | system")
    content: str
    reply_to: Optional[str] = None
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    candidate_id: Optional[str] = None
    mentions: List[str] = Field(default_factory=list)
    reactions: List[Dict[str, Any]] = Field(default_factory=list)  # {"emoji": "👍", "user_id": "..."}
    is_edited: bool = False
    is_pinned: bool = False
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Store read status per user
    read_by: List[str] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)

    def to_mongo(self) -> Dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)

class NotificationModel(BaseModel):
    """Internal MongoDB Notification document model."""
    id: Optional[str] = Field(default=None, alias="_id")
    user_id: str
    type: str = Field(..., description="new_message | mention | added_to_conversation | candidate_shared | reply")
    conversation_id: str
    message_id: Optional[str] = None
    actor_id: str
    content: str
    is_read: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(populate_by_name=True)

    def to_mongo(self) -> Dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)
