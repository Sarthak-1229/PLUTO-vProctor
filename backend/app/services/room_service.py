"""Room lifecycle, state machine, question synchronization, and participant coordination service."""
from __future__ import annotations

import datetime
import hashlib
import json
import secrets
import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.core.errors import AppError
from backend.app.db.models import (
    InterviewReport,
    InterviewRoom,
    InterviewSession,
    Job,
    Question,
    QuestionSet,
    RoomEvent,
    RoomParticipant,
    RoomQuestion,
    SessionQuestion,
    User,
    _utcnow_naive,
)
from backend.app.services.question_set_service import populate_room_questions
from backend.app.services.realtime.transport_adapter import get_media_transport_adapter
from backend.app.services.security_service import record_audit_event


VALID_STATE_TRANSITIONS = {
    "DRAFT": {"SCHEDULED", "LOBBY", "CANCELLED"},
    "SCHEDULED": {"LOBBY", "LIVE", "CANCELLED", "EXPIRED"},
    "LOBBY": {"LIVE", "CANCELLED", "EXPIRED"},
    "LIVE": {"PAUSED", "PROCESSING", "COMPLETED", "CANCELLED"},
    "PAUSED": {"LIVE", "PROCESSING", "COMPLETED", "CANCELLED"},
    "PROCESSING": {"COMPLETED", "FAILED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
    "EXPIRED": set(),
    "FAILED": set(),
}


def _hash_credential(raw: str) -> str:
    return hashlib.sha256(raw.strip().encode("utf-8")).hexdigest()


def generate_room_code() -> str:
    """Generate human-friendly uppercase alphanumeric code e.g. PLUTO-8K9M2P."""
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    suffix = "".join(secrets.choice(chars) for _ in range(6))
    return f"PLUTO-{suffix}"


def generate_invite_token() -> str:
    """Generate cryptographically secure 32-byte URL-safe invite token."""
    return secrets.token_urlsafe(32)


def _append_room_event(
    db: Session,
    room: InterviewRoom,
    *,
    event_type: str,
    actor_user_id: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> RoomEvent:
    next_seq = (room.current_sequence_version or 0) + 1
    room.current_sequence_version = next_seq
    event = RoomEvent(
        id=f"revt_{uuid.uuid4().hex[:12]}",
        room_id=room.id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        payload_json_redacted=payload or {},
        sequence_no=next_seq,
    )
    db.add(event)
    return event


def create_room(
    db: Session,
    *,
    admin_user: User,
    title: str,
    scheduled_at: Optional[datetime.datetime] = None,
    duration_seconds: int = 3600,
    proctoring_preset: str = "strict",
    assigned_candidate_id: Optional[str] = None,
    assigned_candidate_email: Optional[str] = None,
    question_set_id: Optional[str] = None,
    custom_questions: Optional[List[Dict[str, Any]]] = None,
    default_job_id: Optional[str] = None,
    timezone: str = "UTC",
) -> Dict[str, Any]:
    """Create a new collaborative interview room with questions, invites, and participants."""
    t_title = title.strip()
    if not t_title or len(t_title) < 3:
        raise AppError(status_code=422, code="invalid_title", message="Room title must be at least 3 characters.")

    # Resolve assigned candidate if provided
    candidate_user: Optional[User] = None
    if assigned_candidate_id:
        candidate_user = db.query(User).filter(User.id == assigned_candidate_id).first()
        if not candidate_user:
            raise AppError(status_code=404, code="candidate_not_found", message="Assigned candidate not found.")
    elif assigned_candidate_email:
        candidate_user = db.query(User).filter(User.email == assigned_candidate_email.strip().lower()).first()

    raw_code = generate_room_code()
    raw_token = generate_invite_token()

    now = _utcnow_naive()
    expires_at = scheduled_at + datetime.timedelta(seconds=duration_seconds + 7200) if scheduled_at else now + datetime.timedelta(days=7)
    initial_status = "SCHEDULED" if scheduled_at and scheduled_at > now else "LOBBY"

    room_id = f"room_{uuid.uuid4().hex[:12]}"
    room = InterviewRoom(
        id=room_id,
        created_by_admin_id=admin_user.id,
        assigned_candidate_id=candidate_user.id if candidate_user else None,
        room_code_hash=_hash_credential(raw_code),
        invite_token_hash=_hash_credential(raw_token),
        title=t_title,
        status=initial_status,
        scheduled_at=scheduled_at,
        expires_at=expires_at,
        duration_seconds=duration_seconds,
        mode="hosted",
        proctoring_preset=proctoring_preset,
        current_sequence_version=0,
        current_question_ordinal=0,
        question_set_id=question_set_id,
        timezone=timezone,
    )
    db.add(room)

    # Add creator as admin participant
    db.add(
        RoomParticipant(
            id=f"part_{uuid.uuid4().hex[:12]}",
            room_id=room_id,
            user_id=admin_user.id,
            role="admin",
            status="admitted",
        )
    )

    # Add candidate participant if assigned
    if candidate_user:
        db.add(
            RoomParticipant(
                id=f"part_{uuid.uuid4().hex[:12]}",
                room_id=room_id,
                user_id=candidate_user.id,
                role="candidate",
                status="invited",
            )
        )

    # Populate room questions
    populate_room_questions(
        db,
        room_id,
        question_set_id=question_set_id,
        custom_questions=custom_questions,
        default_job_id=default_job_id,
    )

    # Initial creation event
    _append_room_event(
        db,
        room,
        event_type="room.created",
        actor_user_id=admin_user.id,
        payload={"title": t_title, "status": initial_status},
    )

    record_audit_event(
        db,
        action="room.created",
        resource_type="room",
        resource_id=room_id,
        actor_user_id=admin_user.id,
        actor_role=admin_user.role,
        details={"title": t_title, "status": initial_status, "assigned_candidate": candidate_user.id if candidate_user else None},
    )

    db.commit()
    db.refresh(room)
    serialized = serialize_room_summary(room, include_questions=True)
    serialized["raw_room_code"] = raw_code
    serialized["raw_invite_token"] = raw_token
    serialized["invite_url"] = f"/rooms/join?token={raw_token}"
    return serialized


def list_admin_rooms(
    db: Session,
    *,
    admin_user: User,
    status_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List rooms created by this administrator."""
    query = db.query(InterviewRoom)
    if admin_user.role != "super_admin":
        query = query.filter(InterviewRoom.created_by_admin_id == admin_user.id)
    if status_filter:
        query = query.filter(InterviewRoom.status == status_filter)
    rooms = query.order_by(InterviewRoom.created_at.desc()).all()
    return [serialize_room_summary(r) for r in rooms]


def get_room_for_user(
    db: Session,
    room_id: str,
    current_user: User,
) -> InterviewRoom:
    """Authorize access to room for admin creator or assigned/participating candidate."""
    room = db.query(InterviewRoom).filter(InterviewRoom.id == room_id).first()
    if not room:
        raise AppError(status_code=404, code="room_not_found", message="Interview room not found.")

    if current_user.role in ("admin", "super_admin"):
        if current_user.role != "super_admin" and room.created_by_admin_id != current_user.id:
            raise AppError(status_code=403, code="forbidden_room_access", message="You are not authorized to manage this room.")
        return room

    # Candidate check
    is_assigned = room.assigned_candidate_id == current_user.id
    part = db.query(RoomParticipant).filter(RoomParticipant.room_id == room_id, RoomParticipant.user_id == current_user.id).first()
    if not is_assigned and not part:
        raise AppError(status_code=403, code="forbidden_room_access", message="You are not authorized to view this room.")

    return room


def transition_room_state(
    db: Session,
    room: InterviewRoom,
    target_state: str,
    *,
    actor_user: User,
    reason: Optional[str] = None,
) -> None:
    """Enforce server-side authoritative room state machine rules."""
    current_state = room.status
    allowed = VALID_STATE_TRANSITIONS.get(current_state, set())
    if target_state not in allowed:
        raise AppError(
            status_code=409,
            code="invalid_state_transition",
            message=f"Cannot transition interview room from {current_state} to {target_state}.",
        )

    room.status = target_state
    _append_room_event(
        db,
        room,
        event_type="room.state_changed",
        actor_user_id=actor_user.id,
        payload={"from_state": current_state, "to_state": target_state, "reason": reason},
    )


def start_interview_room(
    db: Session,
    room_id: str,
    *,
    admin_user: User,
) -> Dict[str, Any]:
    """Start the hosted interview: transitions room to LIVE and links an active evaluation session."""
    room = get_room_for_user(db, room_id, admin_user)
    now = _utcnow_naive()
    if room.expires_at and room.expires_at < now:
        room.status = "EXPIRED"
        db.commit()
        raise AppError(status_code=400, code="room_expired", message="This interview room has expired and cannot be started.")

    transition_room_state(db, room, "LIVE", actor_user=admin_user)
    room.started_at = now

    # Ensure linked session exists
    if not room.active_session_id:
        sess_id = f"sess_{uuid.uuid4().hex[:12]}"
        cand_name = "Candidate"
        if room.assigned_candidate:
            cand_name = room.assigned_candidate.full_name

        job = db.query(Job).first()
        job_id = job.id if job else "job_sec_analyst"

        session_obj = InterviewSession(
            id=sess_id,
            job_id=job_id,
            candidate_user_id=room.assigned_candidate_id,
            candidate_name=cand_name,
            interview_mode="hosted",
            room_id=room.id,
            interview_status="IN_PROGRESS",
        )
        db.add(session_obj)

        # Mirror RoomQuestions to SessionQuestions for evaluation pipeline parity
        for rq in room.questions:
            valid_qid = None
            if rq.source_question_id:
                if db.query(Question).filter(Question.id == rq.source_question_id).first():
                    valid_qid = rq.source_question_id
            db.add(
                SessionQuestion(
                    session_id=sess_id,
                    question_id=valid_qid,
                    order_index=rq.ordinal,
                    custom_question_text=rq.question_text,
                )
            )

        room.active_session_id = sess_id

    # Activate first question if none active
    first_q = (
        db.query(RoomQuestion)
        .filter(RoomQuestion.room_id == room.id, RoomQuestion.status == "pending")
        .order_by(RoomQuestion.ordinal.asc())
        .first()
    )
    if first_q:
        first_q.status = "active"
        first_q.asked_at = now
        room.current_question_ordinal = first_q.ordinal
        _append_room_event(
            db,
            room,
            event_type="question.active",
            actor_user_id=admin_user.id,
            payload={
                "question_id": first_q.id,
                "ordinal": first_q.ordinal,
                "text": first_q.question_text,
                "time_limit_seconds": first_q.time_limit_seconds,
            },
        )

    db.commit()
    return serialize_room_snapshot(db, room, admin_user)


def pause_interview_room(
    db: Session,
    room_id: str,
    *,
    admin_user: User,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    room = get_room_for_user(db, room_id, admin_user)
    transition_room_state(db, room, "PAUSED", actor_user=admin_user, reason=reason)
    db.commit()
    return serialize_room_snapshot(db, room, admin_user)


def resume_interview_room(
    db: Session,
    room_id: str,
    *,
    admin_user: User,
) -> Dict[str, Any]:
    room = get_room_for_user(db, room_id, admin_user)
    transition_room_state(db, room, "LIVE", actor_user=admin_user)
    db.commit()
    return serialize_room_snapshot(db, room, admin_user)


def advance_room_question(
    db: Session,
    room_id: str,
    *,
    admin_user: User,
    target_ordinal: Optional[int] = None,
) -> Dict[str, Any]:
    """Complete current question and advance to next pending question."""
    room = get_room_for_user(db, room_id, admin_user)
    if room.status not in ("LIVE", "PAUSED"):
        raise AppError(status_code=400, code="room_not_live", message="Cannot advance question when room is not live.")

    now = _utcnow_naive()
    # Mark current active question as answered
    cur_q = (
        db.query(RoomQuestion)
        .filter(RoomQuestion.room_id == room.id, RoomQuestion.status == "active")
        .first()
    )
    if cur_q:
        cur_q.status = "answered"
        cur_q.completed_at = now

    # Determine next question
    query = (
        db.query(RoomQuestion)
        .filter(RoomQuestion.room_id == room.id, RoomQuestion.status == "pending")
    )
    if target_ordinal:
        next_q = query.filter(RoomQuestion.ordinal == target_ordinal).first()
    else:
        next_q = query.order_by(RoomQuestion.ordinal.asc()).first()

    if next_q:
        next_q.status = "active"
        next_q.asked_at = now
        room.current_question_ordinal = next_q.ordinal
        _append_room_event(
            db,
            room,
            event_type="question.active",
            actor_user_id=admin_user.id,
            payload={
                "question_id": next_q.id,
                "ordinal": next_q.ordinal,
                "text": next_q.question_text,
                "time_limit_seconds": next_q.time_limit_seconds,
            },
        )
    else:
        room.current_question_ordinal = 0
        _append_room_event(
            db,
            room,
            event_type="questions.all_completed",
            actor_user_id=admin_user.id,
            payload={},
        )

    db.commit()
    return serialize_room_snapshot(db, room, admin_user)


def skip_room_question(
    db: Session,
    room_id: str,
    *,
    admin_user: User,
) -> Dict[str, Any]:
    """Skip currently active question and advance to next."""
    room = get_room_for_user(db, room_id, admin_user)
    if room.status not in ("LIVE", "PAUSED"):
        raise AppError(status_code=400, code="room_not_live", message="Cannot skip question when room is not live.")

    now = _utcnow_naive()
    cur_q = (
        db.query(RoomQuestion)
        .filter(RoomQuestion.room_id == room.id, RoomQuestion.status == "active")
        .first()
    )
    if cur_q:
        cur_q.status = "skipped"
        cur_q.completed_at = now
        _append_room_event(
            db,
            room,
            event_type="question.skipped",
            actor_user_id=admin_user.id,
            payload={"question_id": cur_q.id, "ordinal": cur_q.ordinal},
        )

    next_q = (
        db.query(RoomQuestion)
        .filter(RoomQuestion.room_id == room.id, RoomQuestion.status == "pending")
        .order_by(RoomQuestion.ordinal.asc())
        .first()
    )
    if next_q:
        next_q.status = "active"
        next_q.asked_at = now
        room.current_question_ordinal = next_q.ordinal
        _append_room_event(
            db,
            room,
            event_type="question.active",
            actor_user_id=admin_user.id,
            payload={
                "question_id": next_q.id,
                "ordinal": next_q.ordinal,
                "text": next_q.question_text,
                "time_limit_seconds": next_q.time_limit_seconds,
            },
        )

    db.commit()
    return serialize_room_snapshot(db, room, admin_user)


def reorder_room_questions(
    db: Session,
    room_id: str,
    *,
    admin_user: User,
    ordered_question_ids: List[str],
) -> Dict[str, Any]:
    """Reorder upcoming pending questions only; historical questions are immutable."""
    room = get_room_for_user(db, room_id, admin_user)
    pending_qs = {
        rq.id: rq
        for rq in db.query(RoomQuestion).filter(RoomQuestion.room_id == room.id, RoomQuestion.status == "pending").all()
    }

    if set(ordered_question_ids) != set(pending_qs.keys()):
        raise AppError(
            status_code=400,
            code="invalid_reorder",
            message="Only currently pending questions can be reordered. Active, answered, and skipped questions cannot be altered.",
        )

    # Base ordinal starts after all non-pending questions
    max_non_pending = (
        db.query(RoomQuestion)
        .filter(RoomQuestion.room_id == room.id, RoomQuestion.status != "pending")
        .count()
    )

    for new_idx, qid in enumerate(ordered_question_ids, start=max_non_pending + 1):
        pending_qs[qid].ordinal = new_idx

    _append_room_event(
        db,
        room,
        event_type="questions.reordered",
        actor_user_id=admin_user.id,
        payload={"ordered_ids": ordered_question_ids},
    )
    db.commit()
    return serialize_room_snapshot(db, room, admin_user)


def end_interview_room(
    db: Session,
    room_id: str,
    *,
    admin_user: User,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """End the live interview, finalizing recordings and evaluation session."""
    room = get_room_for_user(db, room_id, admin_user)
    now = _utcnow_naive()

    # Complete any remaining active question
    active_q = (
        db.query(RoomQuestion)
        .filter(RoomQuestion.room_id == room.id, RoomQuestion.status == "active")
        .first()
    )
    if active_q:
        active_q.status = "answered"
        active_q.completed_at = now

    transition_room_state(db, room, "COMPLETED", actor_user=admin_user, reason=reason)
    room.ended_at = now

    # Update linked session
    if room.active_session_id:
        sess = db.query(InterviewSession).filter(InterviewSession.id == room.active_session_id).first()
        if sess:
            sess.interview_status = "RECORDED"

    _append_room_event(
        db,
        room,
        event_type="room.ended",
        actor_user_id=admin_user.id,
        payload={"ended_at": now.isoformat()},
    )
    db.commit()
    return serialize_room_snapshot(db, room, admin_user)


def join_room_by_token_or_code(
    db: Session,
    *,
    token_or_code: str,
    current_user: User,
    device_checks: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Candidate or invited participant room admission with secure hash lookup."""
    clean_val = token_or_code.strip()
    if not clean_val:
        raise AppError(status_code=400, code="missing_credentials", message="Room code or invitation token is required.")

    hashed = _hash_credential(clean_val)
    room = (
        db.query(InterviewRoom)
        .filter((InterviewRoom.room_code_hash == hashed) | (InterviewRoom.invite_token_hash == hashed))
        .first()
    )
    if not room:
        raise AppError(status_code=404, code="room_not_found", message="Invalid room code or invitation link.")

    now = _utcnow_naive()
    if room.status in ("CANCELLED", "COMPLETED", "EXPIRED", "FAILED"):
        raise AppError(status_code=410, code="room_closed", message=f"This interview room is {room.status.lower()}.")

    if room.expires_at and room.expires_at < now:
        room.status = "EXPIRED"
        db.commit()
        raise AppError(status_code=410, code="room_expired", message="This interview room invitation has expired.")

    # Candidate ownership check: if room has assigned candidate, caller must match
    if room.assigned_candidate_id and room.assigned_candidate_id != current_user.id and current_user.role not in ("admin", "super_admin"):
        raise AppError(
            status_code=403,
            code="forbidden_room_invite",
            message="This invitation was issued for another registered candidate account.",
        )

    # Bind candidate to room if unassigned
    if not room.assigned_candidate_id and current_user.role == "candidate":
        room.assigned_candidate_id = current_user.id

    part = (
        db.query(RoomParticipant)
        .filter(RoomParticipant.room_id == room.id, RoomParticipant.user_id == current_user.id)
        .first()
    )

    participant_status = "admitted" if room.status == "LIVE" else "waiting_room"
    if not part:
        part = RoomParticipant(
            id=f"part_{uuid.uuid4().hex[:12]}",
            room_id=room.id,
            user_id=current_user.id,
            role=current_user.role,
            status=participant_status,
            joined_at=now,
            device_checks_json=device_checks or {},
        )
        db.add(part)
    else:
        part.reconnect_count = (part.reconnect_count or 0) + 1
        part.status = participant_status
        if device_checks:
            part.device_checks_json = device_checks

    _append_room_event(
        db,
        room,
        event_type="participant.joined",
        actor_user_id=current_user.id,
        payload={"user_id": current_user.id, "role": current_user.role, "status": participant_status},
    )

    db.commit()

    adapter = get_media_transport_adapter()
    media_creds = adapter.generate_join_credentials(
        room_id=room.id,
        user_id=current_user.id,
        user_name=current_user.full_name,
        role=part.role,
    )

    snapshot = serialize_room_snapshot(db, room, current_user)
    snapshot["participant_status"] = participant_status
    snapshot["media_credentials"] = media_creds
    return snapshot


def serialize_room_summary(room: InterviewRoom, include_questions: bool = False) -> Dict[str, Any]:
    out = {
        "id": room.id,
        "title": room.title,
        "status": room.status,
        "mode": room.mode,
        "proctoring_preset": room.proctoring_preset,
        "scheduled_at": room.scheduled_at.isoformat() if room.scheduled_at else None,
        "expires_at": room.expires_at.isoformat() if room.expires_at else None,
        "duration_seconds": room.duration_seconds,
        "current_sequence_version": room.current_sequence_version,
        "current_question_ordinal": room.current_question_ordinal,
        "assigned_candidate_id": room.assigned_candidate_id,
        "created_by_admin_id": room.created_by_admin_id,
        "started_at": room.started_at.isoformat() if room.started_at else None,
        "ended_at": room.ended_at.isoformat() if room.ended_at else None,
        "created_at": room.created_at.isoformat() if room.created_at else None,
        "question_count": len(room.questions) if room.questions else 0,
        "participant_count": len(room.participants) if room.participants else 0,
    }
    if include_questions and room.questions:
        out["questions"] = [
            {
                "id": q.id,
                "ordinal": q.ordinal,
                "question_text": q.question_text,
                "domain": q.domain,
                "difficulty": q.difficulty,
                "status": q.status,
                "time_limit_seconds": q.time_limit_seconds,
            }
            for q in room.questions
        ]
    return out


def serialize_room_snapshot(db: Session, room: InterviewRoom, current_user: User) -> Dict[str, Any]:
    adapter = get_media_transport_adapter()
    is_admin = current_user.role in ("admin", "super_admin")

    # Current active question details
    active_q = (
        db.query(RoomQuestion)
        .filter(RoomQuestion.room_id == room.id, RoomQuestion.status == "active")
        .first()
    )
    active_payload = None
    if active_q:
        elapsed = 0
        if active_q.asked_at:
            elapsed = max(0, int((_utcnow_naive() - active_q.asked_at).total_seconds()))
        active_payload = {
            "id": active_q.id,
            "ordinal": active_q.ordinal,
            "text": active_q.question_text,
            "domain": active_q.domain,
            "difficulty": active_q.difficulty,
            "time_limit_seconds": active_q.time_limit_seconds,
            "elapsed_seconds": elapsed,
        }

    # Questions list: Candidates only see full text of active/answered questions; pending questions show ordinal
    questions_list = []
    for q in (room.questions or []):
        if is_admin or q.status in ("active", "answered"):
            questions_list.append({
                "id": q.id,
                "ordinal": q.ordinal,
                "question_text": q.question_text,
                "domain": q.domain,
                "difficulty": q.difficulty,
                "status": q.status,
                "time_limit_seconds": q.time_limit_seconds,
            })
        else:
            questions_list.append({
                "id": q.id,
                "ordinal": q.ordinal,
                "status": q.status,
                "time_limit_seconds": q.time_limit_seconds,
            })

    # Participants
    participants_list = [
        {
            "user_id": p.user_id,
            "role": p.role,
            "status": p.status,
            "reconnect_count": p.reconnect_count,
        }
        for p in (room.participants or [])
    ]

    return {
        "room_id": room.id,
        "title": room.title,
        "status": room.status,
        "current_sequence_version": room.current_sequence_version,
        "current_question_ordinal": room.current_question_ordinal,
        "current_question": active_payload,
        "questions": questions_list,
        "participants": participants_list,
        "scheduled_at": room.scheduled_at.isoformat() if room.scheduled_at else None,
        "started_at": room.started_at.isoformat() if room.started_at else None,
        "ended_at": room.ended_at.isoformat() if room.ended_at else None,
        "ice_servers": adapter.get_ice_servers(),
        "proctoring_preset": room.proctoring_preset,
    }
