"""API endpoints for resume upload, parsing, and candidate screening."""
from __future__ import annotations

import uuid
from typing import Any, Dict
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.db.database import get_db
from backend.app.db.models import InterviewSession, Job
from backend.app.services.resume_service import resume_service

router = APIRouter(prefix="/api/resume", tags=["Resume"])


@router.post("/upload", response_model=Dict[str, Any])
async def upload_resume(
    job_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload resume (PDF/DOCX), parse sections/skills, and evaluate candidate fit."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    # Validate file type
    filename = file.filename or "resume.pdf"
    fn_lower = filename.lower()
    if not (fn_lower.endswith(".pdf") or fn_lower.endswith(".docx") or fn_lower.endswith(".txt")):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Please upload a PDF or DOCX resume.",
        )

    # Read bytes
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Save to storage
    storage_dir = settings.STORAGE_DIR / "resumes"
    storage_dir.mkdir(parents=True, exist_ok=True)
    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    saved_path = storage_dir / f"{session_id}_{filename}"
    saved_path.write_bytes(file_bytes)

    # Parse resume
    parsed = resume_service.parse_resume(file_bytes, filename)

    # Compute fit
    job_dict = {
        "required_skills": job.required_skills or [],
        "preferred_skills": job.preferred_skills or [],
        "min_experience_years": job.min_experience_years,
        "education_levels": job.education_levels or [],
        "pass_threshold": job.pass_threshold,
        "skill_weights": job.skill_weights or {},
    }
    screening = resume_service.calculate_fit(parsed, job_dict)

    # Create session record in database
    session_obj = InterviewSession(
        id=session_id,
        job_id=job.id,
        candidate_name=parsed.get("candidate_name", "Candidate"),
        resume_filename=filename,
        resume_text=parsed.get("raw_text", ""),
        parsed_resume={
            "candidate_name": parsed.get("candidate_name"),
            "skills": parsed.get("skills", []),
            "experience_years": parsed.get("experience_years", 0.0),
            "education": parsed.get("education", {}),
            "sections": {k: v[:200] for k, v in parsed.get("sections", {}).items()},
        },
        screening_fit=screening["fit_score"],
        screening_status=screening["status"],
        screening_details=screening,
        interview_status="CREATED",
    )
    db.add(session_obj)
    db.commit()

    return {
        "session_id": session_id,
        "job_id": job.id,
        "job_title": job.title,
        "company": job.company,
        "candidate_name": parsed.get("candidate_name"),
        "fit_score": screening.get("fit_score", 0.0),
        "decision": screening.get("decision", screening.get("status", "PASS")),
        "status": screening.get("status", "PASS"),
        "skill_score": screening.get("skill_score", 0.0),
        "experience_years": parsed.get("experience_years", 0.0),
        "matched_skills": screening.get("matched_skills", []),
        "missing_skills": screening.get("missing_skills", []),
        "parsed_resume": {
            "skills": parsed.get("skills", []),
            "experience_years": parsed.get("experience_years", 0.0),
            "education": parsed.get("education", {}),
        },
        "screening": screening,
    }
