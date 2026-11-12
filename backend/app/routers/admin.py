"""Administrator console router: legacy session claiming, user governance, and audit logs."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.db.database import get_db
from backend.app.db.models import AuditLog, InterviewReport, InterviewSession, Job, User
from backend.app.services.auth_service import serialize_user
from backend.app.services.authorization import ADMIN_ROLES, require_roles
from backend.app.services.security_service import record_audit_event, utcnow_naive

router = APIRouter(prefix="/api/admin", tags=["Administration"])


class ClaimLegacySessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_user_id: str = Field(..., min_length=4, max_length=64)
    reason: str = Field(..., min_length=5, max_length=500)
    force: bool = False


class UpdateUserRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(..., pattern="^(candidate|admin|super_admin)$")
    reason: str = Field(..., min_length=5, max_length=500)


@router.get("/users")
def list_users(
    role: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    _admin: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    """List user accounts cleanly without exposing sensitive credential material."""
    q = db.query(User)
    if role:
        q = q.filter(User.role == role.strip().lower())
    if search:
        term = f"%{search.strip().lower()}%"
        q = q.filter((User.email.ilike(term)) | (User.full_name.ilike(term)))
    users = q.order_by(User.created_at.desc()).limit(limit).all()
    return {"users": [serialize_user(u) for u in users]}


@router.get("/legacy-sessions")
def list_legacy_sessions(
    include_claimed: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    _admin: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    """List unclaimed (or all) interview sessions for explicit admin claim/linking workflow."""
    q = (
        db.query(InterviewSession, Job, InterviewReport, User)
        .outerjoin(Job, InterviewSession.job_id == Job.id)
        .outerjoin(InterviewReport, InterviewReport.session_id == InterviewSession.id)
        .outerjoin(User, InterviewSession.candidate_user_id == User.id)
    )
    if not include_claimed:
        q = q.filter(InterviewSession.candidate_user_id.is_(None))
    rows = q.order_by(InterviewSession.created_at.desc()).limit(limit).all()

    results = []
    for sess, job, report, owner in rows:
        results.append(
            {
                "session_id": sess.id,
                "candidate_name": sess.candidate_name,
                "candidate_user_id": sess.candidate_user_id,
                "owner_email": owner.email if owner else None,
                "job_id": sess.job_id,
                "job_title": job.title if job else sess.job_id,
                "company": job.company if job else "",
                "interview_mode": sess.interview_mode,
                "interview_status": sess.interview_status,
                "screening_fit": sess.screening_fit,
                "overall_score": report.overall_score if report else None,
                "grade": report.grade if report else None,
                "created_at": sess.created_at.isoformat() if sess.created_at else None,
            }
        )
    return {"sessions": results}


@router.post("/sessions/{sid}/claim")
def claim_legacy_session(
    sid: str,
    payload: ClaimLegacySessionRequest,
    request: Request,
    admin_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    """Explicitly link an unclaimed or reassigned interview session to a verified user with audit logging."""
    session_obj = db.query(InterviewSession).filter(InterviewSession.id == sid).first()
    if session_obj is None:
        raise AppError(status_code=404, code="session_not_found", message="Interview session not found.")

    target_user = db.query(User).filter(User.id == payload.target_user_id).first()
    if target_user is None or not target_user.is_active:
        raise AppError(status_code=404, code="target_user_not_found", message="Target candidate account not found or inactive.")

    if session_obj.candidate_user_id is not None and not payload.force:
        raise AppError(
            status_code=409,
            code="session_already_claimed",
            message="Session is already assigned to an account. Pass force=true to reassign.",
        )

    previous_owner_id = session_obj.candidate_user_id
    session_obj.candidate_user_id = target_user.id
    session_obj.updated_at = utcnow_naive()

    record_audit_event(
        db,
        action="admin.legacy_session_claimed",
        resource_type="session",
        resource_id=sid,
        actor_user_id=admin_user.id,
        actor_role=admin_user.role,
        details={
            "previous_owner_user_id": previous_owner_id,
            "target_user_id": target_user.id,
            "target_email": target_user.email,
            "reason": payload.reason.strip(),
            "forced": bool(payload.force),
        },
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    return {
        "status": "claimed",
        "session": {
            "session_id": session_obj.id,
            "candidate_user_id": session_obj.candidate_user_id,
            "candidate_name": session_obj.candidate_name,
        },
    }


@router.post("/users/{uid}/role")
def update_user_role(
    uid: str,
    payload: UpdateUserRoleRequest,
    request: Request,
    super_admin: User = Depends(require_roles("super_admin")),
    db: Session = Depends(get_db),
):
    """Update a user's platform role (restricted strictly to super_admin) and record audit trail."""
    target = db.query(User).filter(User.id == uid).first()
    if target is None:
        raise AppError(status_code=404, code="user_not_found", message="User not found.")

    if target.id == super_admin.id and payload.role != "super_admin":
        raise AppError(status_code=400, code="cannot_demote_self", message="Super admin cannot demote themselves.")

    previous_role = target.role
    target.role = payload.role
    target.token_version = int(target.token_version or 0) + 1
    target.updated_at = utcnow_naive()

    record_audit_event(
        db,
        action="admin.user_role_updated",
        resource_type="user",
        resource_id=target.id,
        actor_user_id=super_admin.id,
        actor_role=super_admin.role,
        details={
            "previous_role": previous_role,
            "new_role": payload.role,
            "reason": payload.reason.strip(),
        },
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return {"user": serialize_user(target)}


@router.get("/audit-logs")
def get_audit_logs(
    action: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    _admin: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    """Retrieve security & administrative audit log trail sorted newest first."""
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == action.strip())
    rows = q.order_by(AuditLog.created_at.desc()).limit(limit).all()
    return {
        "audit_logs": [
            {
                "id": r.id,
                "actor_user_id": r.actor_user_id,
                "actor_role": r.actor_role,
                "action": r.action,
                "resource_type": r.resource_type,
                "resource_id": r.resource_id,
                "details": r.details_json or {},
                "ip_address": r.ip_address,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }

