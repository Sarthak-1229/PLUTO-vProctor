"""API endpoints for admin interview room creation, question controls, and live orchestration."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.db.database import get_db
from backend.app.db.models import InterviewRoom, User
from backend.app.services.authorization import require_roles
from backend.app.services.realtime.connection_manager import room_manager
from backend.app.services.room_service import (
    advance_room_question,
    create_room,
    end_interview_room,
    generate_invite_token,
    generate_room_code,
    get_room_for_user,
    list_admin_rooms,
    pause_interview_room,
    reorder_room_questions,
    resume_interview_room,
    serialize_room_snapshot,
    serialize_room_summary,
    skip_room_question,
    start_interview_room,
    transition_room_state,
    _hash_credential,
)
from backend.app.services.security_service import record_audit_event

router = APIRouter(prefix="/api/admin/rooms", tags=["Admin Rooms"])


def _broadcast_snapshot_background(room_id: str, snapshot: Dict[str, Any]) -> None:
    """Best-effort async notification to connected participants."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(
            room_manager.broadcast_to_room(
                room_id,
                {"type": "room.snapshot", "snapshot": snapshot},
            )
        )
    except RuntimeError:
        pass


class CreateRoomSchema(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    scheduled_at: Optional[datetime] = None
    duration_seconds: Optional[int] = 3600
    proctoring_preset: Optional[str] = "strict"
    assigned_candidate_id: Optional[str] = None
    assigned_candidate_email: Optional[str] = None
    question_set_id: Optional[str] = None
    custom_questions: Optional[List[Dict[str, Any]]] = None
    default_job_id: Optional[str] = None
    timezone: Optional[str] = "UTC"


class ReorderQuestionsSchema(BaseModel):
    ordered_question_ids: List[str] = Field(..., min_length=1)


class RoomActionSchema(BaseModel):
    reason: Optional[str] = None


@router.post("", response_model=Dict[str, Any], status_code=201)
def create_room_endpoint(
    payload: CreateRoomSchema,
    admin_user: User = Depends(require_roles(["admin", "super_admin"])),
    db: Session = Depends(get_db),
):
    """Create a new interview room with custom or catalog questions."""
    return create_room(
        db,
        admin_user=admin_user,
        title=payload.title,
        scheduled_at=payload.scheduled_at,
        duration_seconds=payload.duration_seconds or 3600,
        proctoring_preset=payload.proctoring_preset or "strict",
        assigned_candidate_id=payload.assigned_candidate_id,
        assigned_candidate_email=payload.assigned_candidate_email,
        question_set_id=payload.question_set_id,
        custom_questions=payload.custom_questions,
        default_job_id=payload.default_job_id,
        timezone=payload.timezone or "UTC",
    )


@router.get("", response_model=List[Dict[str, Any]])
def list_rooms_endpoint(
    status: Optional[str] = None,
    admin_user: User = Depends(require_roles(["admin", "super_admin"])),
    db: Session = Depends(get_db),
):
    """List interview rooms managed by this administrator."""
    return list_admin_rooms(db, admin_user=admin_user, status_filter=status)


@router.get("/{room_id}", response_model=Dict[str, Any])
def get_room_endpoint(
    room_id: str,
    admin_user: User = Depends(require_roles(["admin", "super_admin"])),
    db: Session = Depends(get_db),
):
    """Get full details of a specific room including question set and sequence status."""
    room = get_room_for_user(db, room_id, admin_user)
    return serialize_room_summary(room, include_questions=True)


@router.post("/{room_id}/invite", response_model=Dict[str, Any])
def generate_invite_endpoint(
    room_id: str,
    admin_user: User = Depends(require_roles(["admin", "super_admin"])),
    db: Session = Depends(get_db),
):
    """Regenerate or retrieve fresh invitation tokens and room codes."""
    room = get_room_for_user(db, room_id, admin_user)
    raw_code = generate_room_code()
    raw_token = generate_invite_token()

    room.room_code_hash = _hash_credential(raw_code)
    room.invite_token_hash = _hash_credential(raw_token)

    record_audit_event(
        db,
        action="room.invite_regenerated",
        resource_type="room",
        resource_id=room.id,
        actor_user_id=admin_user.id,
        actor_role=admin_user.role,
    )
    db.commit()

    return {
        "room_id": room.id,
        "room_code": raw_code,
        "invite_token": raw_token,
        "invite_url": f"/rooms/join?token={raw_token}",
    }


@router.post("/{room_id}/start", response_model=Dict[str, Any])
def start_room_endpoint(
    room_id: str,
    admin_user: User = Depends(require_roles(["admin", "super_admin"])),
    db: Session = Depends(get_db),
):
    """Start live interview, activate first question, and broadcast snapshot."""
    snapshot = start_interview_room(db, room_id, admin_user=admin_user)
    _broadcast_snapshot_background(room_id, snapshot)
    return snapshot


@router.post("/{room_id}/pause", response_model=Dict[str, Any])
def pause_room_endpoint(
    room_id: str,
    payload: Optional[RoomActionSchema] = None,
    admin_user: User = Depends(require_roles(["admin", "super_admin"])),
    db: Session = Depends(get_db),
):
    """Pause live interview session."""
    snapshot = pause_interview_room(
        db,
        room_id,
        admin_user=admin_user,
        reason=payload.reason if payload else None,
    )
    _broadcast_snapshot_background(room_id, snapshot)
    return snapshot


@router.post("/{room_id}/resume", response_model=Dict[str, Any])
def resume_room_endpoint(
    room_id: str,
    admin_user: User = Depends(require_roles(["admin", "super_admin"])),
    db: Session = Depends(get_db),
):
    """Resume paused live interview."""
    snapshot = resume_interview_room(db, room_id, admin_user=admin_user)
    _broadcast_snapshot_background(room_id, snapshot)
    return snapshot


@router.post("/{room_id}/advance", response_model=Dict[str, Any])
def advance_question_endpoint(
    room_id: str,
    admin_user: User = Depends(require_roles(["admin", "super_admin"])),
    db: Session = Depends(get_db),
):
    """Advance to the next question in the room."""
    snapshot = advance_room_question(db, room_id, admin_user=admin_user)
    _broadcast_snapshot_background(room_id, snapshot)
    return snapshot


@router.post("/{room_id}/skip", response_model=Dict[str, Any])
def skip_question_endpoint(
    room_id: str,
    admin_user: User = Depends(require_roles(["admin", "super_admin"])),
    db: Session = Depends(get_db),
):
    """Skip currently active question."""
    snapshot = skip_room_question(db, room_id, admin_user=admin_user)
    _broadcast_snapshot_background(room_id, snapshot)
    return snapshot


@router.post("/{room_id}/reorder", response_model=Dict[str, Any])
def reorder_questions_endpoint(
    room_id: str,
    payload: ReorderQuestionsSchema,
    admin_user: User = Depends(require_roles(["admin", "super_admin"])),
    db: Session = Depends(get_db),
):
    """Reorder upcoming pending questions (historical/active questions are immutable)."""
    snapshot = reorder_room_questions(
        db,
        room_id,
        admin_user=admin_user,
        ordered_question_ids=payload.ordered_question_ids,
    )
    _broadcast_snapshot_background(room_id, snapshot)
    return snapshot


@router.post("/{room_id}/end", response_model=Dict[str, Any])
def end_room_endpoint(
    room_id: str,
    payload: Optional[RoomActionSchema] = None,
    admin_user: User = Depends(require_roles(["admin", "super_admin"])),
    db: Session = Depends(get_db),
):
    """End the live interview room and finalize session."""
    snapshot = end_interview_room(
        db,
        room_id,
        admin_user=admin_user,
        reason=payload.reason if payload else None,
    )
    _broadcast_snapshot_background(room_id, snapshot)
    return snapshot


@router.delete("/{room_id}")
def cancel_room_endpoint(
    room_id: str,
    admin_user: User = Depends(require_roles(["admin", "super_admin"])),
    db: Session = Depends(get_db),
):
    """Cancel and archive an interview room."""
    room = get_room_for_user(db, room_id, admin_user)
    if room.status in ("LIVE", "PROCESSING"):
        raise AppError(status_code=400, code="cannot_cancel_live", message="End the live interview before cancelling the room.")

    transition_room_state(db, room, "CANCELLED", actor_user=admin_user)
    db.commit()
    snapshot = serialize_room_snapshot(db, room, admin_user)
    _broadcast_snapshot_background(room_id, snapshot)
    return {"status": "cancelled", "room_id": room_id}

