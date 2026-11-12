"""Authenticated candidate account profile and DB-backed interview history API."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.db.models import CandidateProfile, InterviewReport, InterviewSession, Job, User
from backend.app.services.authorization import get_current_user
from backend.app.services.security_service import record_audit_event, utcnow_naive

router = APIRouter(prefix="/api/candidate", tags=["Candidate Account"])


class CandidateProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: Optional[str] = Field(default=None, min_length=2, max_length=128)
    headline: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=32)
    location: Optional[str] = Field(default=None, max_length=128)
    education_level: Optional[str] = Field(default=None, max_length=64)
    education_details: Optional[List[Dict[str, Any]]] = None
    experience_years: Optional[float] = Field(default=None, ge=0.0, le=60.0)
    experience_summary: Optional[List[Dict[str, Any]]] = None
    technical_skills: Optional[List[str]] = None
    preferred_roles: Optional[List[str]] = None
    portfolio_links: Optional[Dict[str, str]] = None
    bio: Optional[str] = Field(default=None, max_length=4000)


def _get_or_create_profile(db: Session, user: User) -> CandidateProfile:
    prof = db.query(CandidateProfile).filter(CandidateProfile.user_id == user.id).first()
    if prof is not None:
        return prof
    now = utcnow_naive()
    prof = CandidateProfile(
        id=f"cprof_{uuid.uuid4().hex[:16]}",
        user_id=user.id,
        experience_years=0.0,
        technical_skills_json=[],
        preferred_roles_json=[],
        education_details_json=[],
        experience_summary_json=[],
        portfolio_links_json={},
        profile_completed=False,
        created_at=now,
        updated_at=now,
    )
    db.add(prof)
    db.commit()
    db.refresh(prof)
    return prof


def _serialize_profile(user: User, prof: CandidateProfile) -> Dict[str, Any]:
    return {
        "id": prof.id,
        "user_id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "headline": prof.headline,
        "phone": prof.phone,
        "location": prof.location,
        "education_level": prof.education_level,
        "education_details": prof.education_details_json or [],
        "experience_years": float(prof.experience_years or 0.0),
        "experience_summary": prof.experience_summary_json or [],
        "technical_skills": prof.technical_skills_json or [],
        "preferred_roles": prof.preferred_roles_json or [],
        "portfolio_links": prof.portfolio_links_json or {},
        "bio": prof.bio,
        "profile_completed": bool(prof.profile_completed),
        "updated_at": prof.updated_at.isoformat() if prof.updated_at else None,
    }


def _clean_str_list(items: List[str], max_items: int = 50, max_len: int = 80) -> List[str]:
    seen = set()
    cleaned: List[str] = []
    for raw in items:
        val = str(raw).strip()
        if not val:
            continue
        val = val[:max_len]
        key = val.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(val)
        if len(cleaned) >= max_items:
            break
    return cleaned


@router.get("/profile")
def get_candidate_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the authenticated candidate's persisted account profile."""
    prof = _get_or_create_profile(db, current_user)
    return {"profile": _serialize_profile(current_user, prof)}


@router.put("/profile")
def update_candidate_profile(
    payload: CandidateProfileUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update personal, educational, technical skill, and experience details for the current user."""
    prof = _get_or_create_profile(db, current_user)
    now = utcnow_naive()

    if payload.full_name is not None:
        current_user.full_name = payload.full_name.strip()
        current_user.updated_at = now
    if payload.headline is not None:
        prof.headline = payload.headline.strip() or None
    if payload.phone is not None:
        prof.phone = payload.phone.strip() or None
    if payload.location is not None:
        prof.location = payload.location.strip() or None
    if payload.education_level is not None:
        prof.education_level = payload.education_level.strip() or None
    if payload.education_details is not None:
        prof.education_details_json = payload.education_details[:20]
    if payload.experience_years is not None:
        prof.experience_years = float(payload.experience_years)
    if payload.experience_summary is not None:
        prof.experience_summary_json = payload.experience_summary[:25]
    if payload.technical_skills is not None:
        prof.technical_skills_json = _clean_str_list(payload.technical_skills, max_items=60)
    if payload.preferred_roles is not None:
        prof.preferred_roles_json = _clean_str_list(payload.preferred_roles, max_items=20)
    if payload.portfolio_links is not None:
        prof.portfolio_links_json = {
            str(k).strip()[:32]: str(v).strip()[:300]
            for k, v in payload.portfolio_links.items()
            if str(k).strip() and str(v).strip()
        }
    if payload.bio is not None:
        prof.bio = payload.bio.strip() or None

    has_skills = bool(prof.technical_skills_json)
    has_edu_or_headline = bool(prof.education_level or prof.headline or prof.experience_summary_json)
    prof.profile_completed = bool(has_skills and has_edu_or_headline)
    prof.updated_at = now

    record_audit_event(
        db,
        action="candidate.profile_updated",
        resource_type="candidate_profile",
        resource_id=prof.id,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(prof)
    return {"profile": _serialize_profile(current_user, prof)}


@router.get("/history")
def get_candidate_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List interview sessions owned strictly by the authenticated candidate."""
    rows = (
        db.query(InterviewSession, Job, InterviewReport)
        .outerjoin(Job, InterviewSession.job_id == Job.id)
        .outerjoin(InterviewReport, InterviewReport.session_id == InterviewSession.id)
        .filter(InterviewSession.candidate_user_id == current_user.id)
        .order_by(InterviewSession.created_at.desc())
        .all()
    )

    sessions = []
    for sess, job, report in rows:
        sessions.append(
            {
                "session_id": sess.id,
                "job_id": sess.job_id,
                "job_title": job.title if job else sess.job_id,
                "company": job.company if job else "",
                "candidate_name": sess.candidate_name,
                "interview_mode": sess.interview_mode,
                "interview_status": sess.interview_status,
                "screening_fit": sess.screening_fit,
                "screening_status": sess.screening_status,
                "has_report": report is not None,
                "overall_score": report.overall_score if report else None,
                "grade": report.grade if report else None,
                "readiness_label": report.readiness_label if report else None,
                "created_at": sess.created_at.isoformat() if sess.created_at else None,
            }
        )
    return {"sessions": sessions}

