"""Realtime WebSocket connection manager and event dispatcher for interview rooms."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from fastapi import WebSocket

logger = logging.getLogger("pluto.realtime")


class RoomConnectionManager:
    """Manages active WebSockets and delivers synchronized room events and signaling packets."""

    def __init__(self):
        # Map: room_id -> { user_id: { "ws": WebSocket, "role": str, "user_name": str } }
        self._rooms: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self,
        *,
        room_id: str,
        user_id: str,
        user_name: str,
        role: str,
        websocket: WebSocket,
    ) -> None:
        """Register an authorized WebSocket connection for a room participant."""
        async with self._lock:
            if room_id not in self._rooms:
                self._rooms[room_id] = {}
            self._rooms[room_id][user_id] = {
                "ws": websocket,
                "role": role,
                "user_name": user_name,
            }
        logger.info("Participant %s (%s, %s) connected to room %s", user_name, user_id, role, room_id)

    async def disconnect(self, room_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Remove a participant on socket disconnect."""
        async with self._lock:
            if room_id in self._rooms and user_id in self._rooms[room_id]:
                info = self._rooms[room_id].pop(user_id)
                if not self._rooms[room_id]:
                    self._rooms.pop(room_id, None)
                logger.info("Participant %s disconnected from room %s", user_id, room_id)
                return info
        return None

    def get_room_occupants(self, room_id: str) -> List[Dict[str, Any]]:
        """Return connected user metadata for a room."""
        if room_id not in self._rooms:
            return []
        return [
            {"user_id": uid, "role": data["role"], "user_name": data["user_name"]}
            for uid, data in self._rooms[room_id].items()
        ]

    def has_user(self, room_id: str, user_id: str) -> bool:
        return room_id in self._rooms and user_id in self._rooms[room_id]

    async def broadcast_to_room(
        self,
        room_id: str,
        message: Dict[str, Any],
        exclude_user_id: Optional[str] = None,
    ) -> None:
        """Broadcast a structured JSON payload to all connected participants in a room."""
        if room_id not in self._rooms:
            return

        payload_str = json.dumps(message)
        targets = [
            (uid, data["ws"])
            for uid, data in list(self._rooms[room_id].items())
            if exclude_user_id is None or uid != exclude_user_id
        ]

        stale_users = []
        for uid, ws in targets:
            try:
                await ws.send_text(payload_str)
            except Exception as exc:
                logger.warning("Failed sending message to user %s in room %s: %s", uid, room_id, exc)
                stale_users.append(uid)

        if stale_users:
            async with self._lock:
                for uid in stale_users:
                    if room_id in self._rooms and uid in self._rooms[room_id]:
                        self._rooms[room_id].pop(uid, None)

    async def send_to_user(
        self,
        room_id: str,
        target_user_id: str,
        message: Dict[str, Any],
    ) -> bool:
        """Send a direct message (e.g. peer WebRTC signaling offer/answer) to a specific user."""
        if room_id not in self._rooms or target_user_id not in self._rooms[room_id]:
            return False

        ws = self._rooms[room_id][target_user_id]["ws"]
        try:
            await ws.send_text(json.dumps(message))
            return True
        except Exception as exc:
            logger.warning("Failed direct message to %s in room %s: %s", target_user_id, room_id, exc)
            return False


room_manager = RoomConnectionManager()

