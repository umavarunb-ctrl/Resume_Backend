import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, HTTPException, status

from app.api.dependencies import (
    get_current_user,
    get_conversation_service,
    get_message_service,
    get_notification_service,
    get_user_repository,
    get_auth_service
)
from app.schemas.auth import UserResponse
from app.schemas.chat import (
    CreateConversationRequest,
    UpdateConversationRequest,
    AddMemberRequest,
    SendMessageRequest,
    UpdateMessageRequest,
    ReactionRequest,
    ShareCandidateRequest
)
from app.services.chat.conversation_service import ConversationService
from app.services.chat.message_service import MessageService
from app.services.chat.notification_service import NotificationService
from app.services.chat.websocket_manager import ws_manager
from app.services.auth_service import AuthService
from app.core.security import decode_access_token
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# --- REST APIs ---

@router.post("/conversations")
def create_conversation(
    req: CreateConversationRequest,
    current_user: UserResponse = Depends(get_current_user),
    conv_service: ConversationService = Depends(get_conversation_service)
):
    return conv_service.create_conversation(req, current_user.id)

@router.get("/conversations")
def get_conversations(
    limit: int = Query(30, ge=1, le=100),
    cursor: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user),
    conv_service: ConversationService = Depends(get_conversation_service)
):
    return conv_service.get_user_conversations(current_user.id, limit, cursor)

@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: str,
    current_user: UserResponse = Depends(get_current_user),
    conv_service: ConversationService = Depends(get_conversation_service)
):
    return conv_service.get_conversation(conversation_id, current_user.id)

@router.patch("/conversations/{conversation_id}")
def update_conversation(
    conversation_id: str,
    req: UpdateConversationRequest,
    current_user: UserResponse = Depends(get_current_user),
    conv_service: ConversationService = Depends(get_conversation_service)
):
    return conv_service.update_conversation(conversation_id, req, current_user.id)

@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    current_user: UserResponse = Depends(get_current_user),
    conv_service: ConversationService = Depends(get_conversation_service)
):
    conv_service.delete_conversation(conversation_id, current_user.id)
    return {"success": True}

@router.post("/conversations/{conversation_id}/members")
def add_members(
    conversation_id: str,
    req: AddMemberRequest,
    current_user: UserResponse = Depends(get_current_user),
    conv_service: ConversationService = Depends(get_conversation_service)
):
    return conv_service.add_members(conversation_id, req, current_user.id)

@router.delete("/conversations/{conversation_id}/members/{user_id}")
def remove_member(
    conversation_id: str,
    user_id: str,
    current_user: UserResponse = Depends(get_current_user),
    conv_service: ConversationService = Depends(get_conversation_service)
):
    conv_service.remove_member(conversation_id, user_id, current_user.id)
    return {"success": True}

@router.get("/conversations/{conversation_id}/messages")
def get_messages(
    conversation_id: str,
    limit: int = Query(50, ge=1, le=100),
    cursor: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user),
    msg_service: MessageService = Depends(get_message_service)
):
    return msg_service.get_messages(conversation_id, current_user.id, limit, cursor)

@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    req: SendMessageRequest,
    current_user: UserResponse = Depends(get_current_user),
    msg_service: MessageService = Depends(get_message_service)
):
    return await msg_service.send_message(conversation_id, req, current_user.id)

@router.patch("/messages/{message_id}")
async def update_message(
    message_id: str,
    req: UpdateMessageRequest,
    current_user: UserResponse = Depends(get_current_user),
    msg_service: MessageService = Depends(get_message_service)
):
    return await msg_service.update_message(message_id, req, current_user.id)

@router.delete("/messages/{message_id}")
async def delete_message(
    message_id: str,
    current_user: UserResponse = Depends(get_current_user),
    msg_service: MessageService = Depends(get_message_service)
):
    await msg_service.delete_message(message_id, current_user.id)
    return {"success": True}

@router.post("/messages/{message_id}/reactions")
async def toggle_reaction(
    message_id: str,
    req: ReactionRequest,
    current_user: UserResponse = Depends(get_current_user),
    msg_service: MessageService = Depends(get_message_service)
):
    await msg_service.toggle_reaction(message_id, req, current_user.id)
    return {"success": True}

@router.post("/messages/{message_id}/pin")
async def pin_message(
    message_id: str,
    current_user: UserResponse = Depends(get_current_user),
    msg_service: MessageService = Depends(get_message_service)
):
    await msg_service.toggle_pin(message_id, True, current_user.id)
    return {"success": True}

@router.delete("/messages/{message_id}/pin")
async def unpin_message(
    message_id: str,
    current_user: UserResponse = Depends(get_current_user),
    msg_service: MessageService = Depends(get_message_service)
):
    await msg_service.toggle_pin(message_id, False, current_user.id)
    return {"success": True}

@router.get("/users/search")
def search_chat_users(
    q: str,
    limit: int = Query(20, ge=1, le=50),
    current_user: UserResponse = Depends(get_current_user),
    user_repo: UserRepository = Depends(get_user_repository),
    auth_service: AuthService = Depends(get_auth_service)
):
    # Only internal users can search other internal users
    if current_user.role not in ["recruiter", "senior_recruiter", "hiring_manager", "admin"]:
        raise HTTPException(status_code=403, detail="Not authorized to search chat users")
        
    allowed_roles = ["recruiter", "senior_recruiter", "hiring_manager", "admin"]
    users = user_repo.search_internal_users(q, allowed_roles, limit)
    
    result = []
    for u in users:
        pic = u.get("profile_picture")
        if pic and pic.startswith("oci:"):
            try:
                pic = auth_service.get_profile_picture_url(str(u["_id"]))
            except Exception:
                logger.warning("Failed to generate profile picture URL for user %s", u["_id"])
                pic = None
            
        result.append({
            "id": str(u["_id"]),
            "full_name": u["full_name"],
            "email": u["email"],
            "profile_picture": pic,
            "role": u.get("role")
        })
        
    return {"users": result}

@router.get("/users/{user_id}")
def get_chat_user(
    user_id: str,
    current_user: UserResponse = Depends(get_current_user),
    user_repo: UserRepository = Depends(get_user_repository),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Fetch a single internal user's public profile by their ID.
    Used by the chat sidebar to resolve display names and avatars."""
    if current_user.role not in ["recruiter", "senior_recruiter", "hiring_manager", "admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    user = user_repo.find_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    pic = user.get("profile_picture")
    if pic and pic.startswith("oci:"):
        try:
            pic = auth_service.get_profile_picture_url(str(user["_id"]))
        except Exception:
            logger.warning("Failed to generate profile picture URL for user %s", user["_id"])
            pic = None

    return {
        "id": str(user["_id"]),
        "full_name": user.get("full_name", "Unknown User"),
        "email": user.get("email"),
        "profile_picture": pic,
        "role": user.get("role")
    }

@router.post("/conversations/{conversation_id}/read")
def mark_conversation_read(
    conversation_id: str,
    current_user: UserResponse = Depends(get_current_user),
    msg_service: MessageService = Depends(get_message_service)
):
    msg_service.mark_conversation_read(conversation_id, current_user.id)
    return {"success": True}

@router.get("/search")
def search_conversations(
    q: str,
    current_user: UserResponse = Depends(get_current_user),
    conv_service: ConversationService = Depends(get_conversation_service)
):
    return conv_service.search_conversations(current_user.id, q)

@router.get("/notifications")
def get_notifications(
    limit: int = Query(50, ge=1, le=100),
    cursor: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user),
    notif_service: NotificationService = Depends(get_notification_service)
):
    return notif_service.get_notifications(current_user.id, limit, cursor)

@router.post("/notifications/read-all")
def mark_all_notifications_read(
    current_user: UserResponse = Depends(get_current_user),
    notif_service: NotificationService = Depends(get_notification_service)
):
    notif_service.mark_all_read(current_user.id)
    return {"success": True}

@router.post("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    current_user: UserResponse = Depends(get_current_user),
    notif_service: NotificationService = Depends(get_notification_service)
):
    notif_service.mark_read(notification_id, current_user.id)
    return {"success": True}


@router.get("/presence")
def get_presence(
    current_user: UserResponse = Depends(get_current_user)
):
    """Return all currently online internal users connected via WebSocket."""
    return {"online_users": ws_manager.get_online_users()}

@router.post("/conversations/{conversation_id}/candidate")
async def share_candidate(
    conversation_id: str,
    req: ShareCandidateRequest,
    current_user: UserResponse = Depends(get_current_user),
    msg_service: MessageService = Depends(get_message_service)
):
    return await msg_service.share_candidate(conversation_id, req, current_user.id)

# --- WebSockets ---

@router.websocket("/ws")
async def chat_websocket(
    websocket: WebSocket,
    token: str = Query(...)
):
    # Verify token
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
        
    user_id = payload.get("sub")
    
    await ws_manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                event_data = json.loads(data)
                event_type = event_data.get("event")
                conv_id = event_data.get("conversation_id")

                if event_type == "subscribe" and conv_id:
                    ws_manager.subscribe(conv_id, user_id)
                elif event_type == "unsubscribe" and conv_id:
                    ws_manager.unsubscribe(conv_id, user_id)
                elif event_type in ["typing.started", "typing.stopped"] and conv_id:
                    # Broadcast typing event to room
                    await ws_manager.broadcast_to_room(conv_id, {
                        "event": event_type,
                        "conversation_id": conv_id,
                        "data": {"user_id": user_id}
                    })
            except json.JSONDecodeError:
                continue
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, user_id)
    except Exception:
        await ws_manager.disconnect(websocket, user_id)

