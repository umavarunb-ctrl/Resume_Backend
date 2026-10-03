import asyncio
import json
from typing import Dict, List, Set, Any, Optional
from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder

class WebSocketManager:
    def __init__(self):
        # user_id -> set of WebSockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # conversation_id -> set of user_ids (who are online and subscribed)
        self.rooms: Dict[str, Set[str]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        is_first_connection = user_id not in self.active_connections or len(self.active_connections[user_id]) == 0
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)

        # Send presence list (all currently online user IDs) to the newly connected client
        online_users = list(self.active_connections.keys())
        try:
            await websocket.send_text(json.dumps(jsonable_encoder({
                "event": "presence.list",
                "conversation_id": None,
                "data": {
                    "user_ids": online_users,
                    "users": online_users,
                    "online_users": online_users
                },
                "user_ids": online_users
            })))
        except Exception:
            pass

        # If this is the user's first active connection, broadcast user.online to all other connected clients
        if is_first_connection:
            await self.broadcast_all({
                "event": "user.online",
                "conversation_id": None,
                "data": {
                    "user_id": user_id,
                    "userId": user_id
                },
                "user_id": user_id
            }, exclude_user_id=user_id)

    async def disconnect(self, websocket: WebSocket, user_id: str):
        became_offline = False
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                became_offline = True
                # Remove user from all rooms they were in
                for room_id in list(self.rooms.keys()):
                    self.rooms[room_id].discard(user_id)
                    if not self.rooms[room_id]:
                        del self.rooms[room_id]

        # If user has no more active connections, broadcast user.offline to remaining connected clients
        if became_offline:
            await self.broadcast_all({
                "event": "user.offline",
                "conversation_id": None,
                "data": {
                    "user_id": user_id,
                    "userId": user_id
                },
                "user_id": user_id
            })

    def subscribe(self, conversation_id: str, user_id: str):
        if conversation_id not in self.rooms:
            self.rooms[conversation_id] = set()
        self.rooms[conversation_id].add(user_id)

    def unsubscribe(self, conversation_id: str, user_id: str):
        if conversation_id in self.rooms:
            self.rooms[conversation_id].discard(user_id)
            if not self.rooms[conversation_id]:
                del self.rooms[conversation_id]

    async def broadcast_all(self, message: Dict[str, Any], exclude_user_id: Optional[str] = None):
        message_str = json.dumps(jsonable_encoder(message))
        dead_sockets = []
        for uid, sockets in list(self.active_connections.items()):
            if exclude_user_id and uid == exclude_user_id:
                continue
            for ws in list(sockets):
                try:
                    await ws.send_text(message_str)
                except Exception:
                    dead_sockets.append((uid, ws))

        for uid, ws in dead_sockets:
            await self.disconnect(ws, uid)

    async def broadcast_to_room(self, conversation_id: str, message: Dict[str, Any]):
        if conversation_id not in self.rooms:
            return
        
        message_str = json.dumps(jsonable_encoder(message))
        dead_sockets = []
        
        for user_id in list(self.rooms.get(conversation_id, set())):
            if user_id in self.active_connections:
                for ws in list(self.active_connections[user_id]):
                    try:
                        await ws.send_text(message_str)
                    except Exception:
                        dead_sockets.append((user_id, ws))
        
        for user_id, ws in dead_sockets:
            await self.disconnect(ws, user_id)

    async def send_personal_message(self, message: Dict[str, Any], user_id: str):
        if user_id in self.active_connections:
            message_str = json.dumps(jsonable_encoder(message))
            dead_sockets = []
            for ws in list(self.active_connections[user_id]):
                try:
                    await ws.send_text(message_str)
                except Exception:
                    dead_sockets.append((user_id, ws))
            
            for uid, ws in dead_sockets:
                await self.disconnect(ws, uid)

    def get_online_users(self) -> List[str]:
        return list(self.active_connections.keys())

    def is_user_online(self, user_id: str) -> bool:
        return user_id in self.active_connections and len(self.active_connections[user_id]) > 0

# Singleton manager
ws_manager = WebSocketManager()
