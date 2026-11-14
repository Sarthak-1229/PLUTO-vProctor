"""API endpoints and WebSocket signaling for candidate room access and live WebRTC negotiation."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.db.database import get_db, SessionLocal
from backend.app.db.models import InterviewRoom, RoomParticipant, User
from backend.app.services.authorization import get_current_user, require_roles
from backend.app.services.realtime.connection_manager import room_manager
from backend.app.services.realtime.transport_adapter import get_media_transport_adapter
from backend.app.services.room_service import (
    get_room_for_user,
    join_room_by_token_or_code,
    serialize_room_snapshot,
)
from backend.app.services.security_service import decode_access_token

logger = logging.getLogger("pluto.rooms")
router = APIRouter(prefix="/api/rooms", tags=["Candidate Rooms"])


class JoinRoomSchema(BaseModel):
    token_or_code: str = Field(..., min_length=4, max_length=128)
    device_checks: Optional[Dict[str, Any]] = None


class DeviceCheckSchema(BaseModel):
    camera_ok: bool = True
    mic_ok: bool = True
    latency_ms: Optional[float] = None
    browser: Optional[str] = None


@router.post("/join", response_model=Dict[str, Any])
def join_room_endpoint(
    payload: JoinRoomSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Authenticate and join a waiting room via invite link or room code."""
    result = join_room_by_token_or_code(
        db,
        token_or_code=payload.token_or_code,
        current_user=current_user,
        device_checks=payload.device_checks,
    )
    return result


@router.get("/{room_id}/snapshot", response_model=Dict[str, Any])
def get_snapshot_endpoint(
    room_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch authoritative server snapshot of room state and current active question."""
    room = get_room_for_user(db, room_id, current_user)
    return serialize_room_snapshot(db, room, current_user)


@router.post("/{room_id}/device-check")
def submit_device_check_endpoint(
    room_id: str,
    payload: DeviceCheckSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update participant preflight device check status."""
    room = get_room_for_user(db, room_id, current_user)
    part = (
        db.query(RoomParticipant)
        .filter(RoomParticipant.room_id == room.id, RoomParticipant.user_id == current_user.id)
        .first()
    )
    if part:
        part.device_checks_json = payload.model_dump()
        db.commit()
    return {"status": "recorded"}


@router.websocket("/{room_id}/ws")
async def room_websocket_endpoint(
    websocket: WebSocket,
    room_id: str,
    token: Optional[str] = Query(None),
):
    """Authenticated realtime WebSocket connection for room state events and WebRTC signaling."""
    # 1. Authenticate user from query token
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing authentication token")
        return

    db = SessionLocal()
    websocket_accepted = False
    connected_user = None
    try:
        try:
            claims = decode_access_token(token)
            user_id = claims["sub"]
            user = db.query(User).filter(User.id == user_id).first()
            if not user or not user.is_active or user.token_version != claims.get("tv"):
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid credentials")
                return

            room = get_room_for_user(db, room_id, user)
            connected_user = user
        except AppError as exc:
            err_reason = str(getattr(exc, "detail", exc))
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=err_reason[:120])
            return
        except Exception:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication failed")
            return

        # 2. Accept socket connection and register
        await websocket.accept()
        websocket_accepted = True
        await room_manager.connect(
            room_id=room_id,
            user_id=connected_user.id,
            user_name=connected_user.full_name,
            role=connected_user.role,
            websocket=websocket,
        )

        adapter = get_media_transport_adapter()

        # Send initial snapshot and occupants list
        snapshot = serialize_room_snapshot(db, room, connected_user)
        occupants = room_manager.get_room_occupants(room_id)
        await websocket.send_text(
            json.dumps({
                "type": "room.snapshot",
                "snapshot": snapshot,
                "occupants": occupants,
            })
        )

        # Notify peers of arrival
        await room_manager.broadcast_to_room(
            room_id,
            {
                "type": "participant.joined",
                "user_id": connected_user.id,
                "user_name": connected_user.full_name,
                "role": connected_user.role,
            },
            exclude_user_id=connected_user.id,
        )

        # 3. Message loop
        while True:
            text = await websocket.receive_text()
            try:
                msg = json.loads(text)
            except Exception:
                continue

            msg_type = msg.get("type")
            if msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            elif msg_type == "webrtc.signal":
                # Validate signal schema
                signal_type = msg.get("signal_type")
                signal_payload = msg.get("payload") or {}
                if adapter.validate_signal_payload(signal_type, signal_payload):
                    target_id = msg.get("target_user_id")
                    out_packet = {
                        "type": "webrtc.signal",
                        "sender_user_id": connected_user.id,
                        "sender_name": connected_user.full_name,
                        "signal_type": signal_type,
                        "payload": signal_payload,
                    }
                    if target_id:
                        await room_manager.send_to_user(room_id, target_id, out_packet)
                    else:
                        # Broadcast to peer in room
                        await room_manager.broadcast_to_room(
                            room_id,
                            out_packet,
                            exclude_user_id=connected_user.id,
                        )
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for user %s in room %s", connected_user.id if connected_user else "unknown", room_id)
    except Exception as exc:
        logger.warning("WebSocket exception in room %s: %s", room_id, exc)
        if not websocket_accepted:
            try:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Connection error")
            except Exception:
                pass
    finally:
        if websocket_accepted and connected_user:
            await room_manager.disconnect(room_id, connected_user.id)
            await room_manager.broadcast_to_room(
                room_id,
                {"type": "participant.left", "user_id": connected_user.id, "user_name": connected_user.full_name},
                exclude_user_id=connected_user.id,
            )
        db.close()
