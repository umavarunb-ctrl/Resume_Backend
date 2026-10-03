from typing import Optional
from app.models.chat import NotificationModel
from app.repositories.chat.notification_repository import NotificationRepository
from app.services.chat.authorization_service import AuthorizationService

class NotificationService:
    def __init__(self, notif_repo: NotificationRepository, auth_service: AuthorizationService):
        self.notif_repo = notif_repo
        self.auth_service = auth_service

    def get_notifications(self, user_id: str, limit: int = 50, cursor: Optional[str] = None):
        notifs = self.notif_repo.get_user_notifications(user_id, limit + 1, cursor)
        
        has_more = len(notifs) > limit
        if has_more:
            notifs = notifs[:limit]
            
        next_cursor = None
        if notifs:
            next_cursor = str(notifs[-1]["_id"])
            
        for n in notifs:
            n["id"] = str(n.pop("_id", n.get("_id")))

        return {
            "notifications": notifs,
            "has_more": has_more,
            "next_cursor": next_cursor
        }

    def mark_read(self, notification_id: str, user_id: str):
        self.notif_repo.mark_read(notification_id, user_id)

    def mark_all_read(self, user_id: str):
        self.notif_repo.mark_all_read(user_id)

    def create_notification(self, user_id: str, actor_id: str, type: str, conv_id: str, msg_id: str, content: str):
        if user_id == actor_id:
            return # Don't notify self
            
        model = NotificationModel(
            user_id=user_id,
            actor_id=actor_id,
            type=type,
            conversation_id=conv_id,
            message_id=msg_id,
            content=content
        )
        self.notif_repo.create(model.to_mongo())
