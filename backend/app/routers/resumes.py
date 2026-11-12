"""Candidate multi-resume library and editable parsed resume-profile endpoints."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.db.models import User
from backend.app.services.authorization import get_current_user
from backend.app.services.resume_profile_service import (
    confirm_resume_profile,
    create_interview_session_from_saved_resume,
    delete_resume_completely,
    get_resume_for_user,
    list_user_resumes,
    update_resume_profile_fields,
    upload_and_parse_resume,
)

router = APIRouter(prefix="/api/resumes", tags=["Resume Library"])


class ResumeProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    skills: Optional[List[str]] = None
    experience_years: Optional[float] = Field(default=None, ge=0.0, le=60.0)
    education: Optional[Dict[str, Any]] = None
    summary: Optional[str] = Field(default=None, max_length=4000)


@router.get("")
def list_my_resumes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List saved resumes and extracted/confirmed profiles for the authenticated candidate."""
    return {"resumes": list_user_resumes(db, current_user.id)}


@router.post("/upload", status_code=201)
async def upload_resume_to_library(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Validate, privately store, and parse a candidate resume into the persistent library."""
    file_bytes = await file.read()
    return upload_and_parse_resume(
        db,
        user=current_user,
        filename=file.filename or "resume.pdf",
        content_type=file.content_type,
        file_bytes=file_bytes,
        ip_address=request.client.host if request.client else None,
    )


@router.get("/{resume_id}")
def get_my_resume(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve a candidate's stored resume metadata and parsed/edited profile."""
    return get_resume_for_user(db, resume_id, current_user)


@router.put("/{resume_id}/profile")
def edit_my_resume_profile(
    resume_id: str,
    payload: ResumeProfileUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Allow candidate to review and edit extracted resume fields before confirmation."""
    return update_resume_profile_fields(
        db,
        resume_id=resume_id,
        user=current_user,
        updates=payload.model_dump(exclude_unset=True),
        ip_address=request.client.host if request.client else None,
    )


@router.post("/{resume_id}/confirm")
def confirm_my_resume_profile(
    resume_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark reviewed resume profile fields as confirmed by the candidate."""
    return confirm_resume_profile(
        db,
        resume_id=resume_id,
        user=current_user,
        ip_address=request.client.host if request.client else None,
    )


@router.delete("/{resume_id}")
def delete_my_resume(
    resume_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a resume and its parsed profile plus private disk artifact cleanly."""
    delete_resume_completely(
        db,
        resume_id=resume_id,
        user=current_user,
        ip_address=request.client.host if request.client else None,
    )
    return {"status": "deleted", "resume_id": resume_id}


@router.post("/{resume_id}/start-session")
def start_session_from_saved_resume(
    resume_id: str,
    job_id: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a job screening session using a previously saved/confirmed resume."""
    return create_interview_session_from_saved_resume(
        db,
        resume_id=resume_id,
        job_id=job_id,
        user=current_user,
    )

