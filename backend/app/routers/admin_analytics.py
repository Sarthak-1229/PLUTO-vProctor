"""Administrator operations monitoring, platform throughput, and interview analytics."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.db.models import AuditLog, InterviewReport, InterviewRoom, InterviewSession, ProctoringEvent, User
from backend.app.services.authorization import require_roles

router = APIRouter(prefix="/api/admin/analytics", tags=["admin-analytics"])


@router.get("/overview")
def get_admin_overview_analytics(
    current_admin: User = Depends(require_roles(["admin", "super_admin"])),
    db: Session = Depends(get_db),
):
    """Aggregate high-level platform throughput, user counts, and proctoring metrics."""
    total_candidates = db.query(User).filter(User.role == "candidate").count()
    total_admins = db.query(User).filter(User.role.in_(["admin", "super_admin"])).count()

    total_sessions = db.query(InterviewSession).count()
    self_practice_sessions = db.query(InterviewSession).filter(InterviewSession.interview_mode == "self_practice").count()
    hosted_sessions = db.query(InterviewSession).filter(InterviewSession.interview_mode == "hosted").count()

    reports = db.query(InterviewReport).all()
    avg_score = round(sum(r.overall_score for r in reports) / max(len(reports), 1), 1) if reports else 0.0

    total_rooms = db.query(InterviewRoom).count()
    active_rooms = db.query(InterviewRoom).filter(InterviewRoom.status.in_(["LOBBY", "LIVE", "PAUSED"])).count()
    completed_rooms = db.query(InterviewRoom).filter(InterviewRoom.status == "COMPLETED").count()

    total_proctoring_infractions = db.query(ProctoringEvent).count()

    return {
        "users": {
            "total_candidates": total_candidates,
            "total_admins": total_admins,
        },
        "interviews": {
            "total_sessions": total_sessions,
            "self_practice_count": self_practice_sessions,
            "hosted_count": hosted_sessions,
            "completed_reports_count": len(reports),
            "average_overall_score": avg_score,
        },
        "rooms": {
            "total_rooms": total_rooms,
            "active_now": active_rooms,
            "completed": completed_rooms,
        },
        "proctoring": {
            "total_infractions_detected": total_proctoring_infractions,
        },
    }


@router.get("/activity")
def get_recent_activity_feed(
    current_admin: User = Depends(require_roles(["admin", "super_admin"])),
    limit: int = Query(25, ge=5, le=100),
    db: Session = Depends(get_db),
):
    """Retrieve chronologically ordered operational events and audit log records."""
    logs = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "activity": [
            {
                "id": l.id,
                "action": l.action,
                "actor_role": l.actor_role,
                "actor_user_id": l.actor_user_id,
                "resource_type": l.resource_type,
                "resource_id": l.resource_id,
                "details": l.details_json,
                "timestamp": l.created_at.isoformat() if l.created_at else None,
            }
            for l in logs
        ]
    }

