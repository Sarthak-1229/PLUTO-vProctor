"""API endpoints for resume upload, parsing, and candidate screening."""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.db.database import get_db
from backend.app.db.models import InterviewSession, Job
from backend.app.services.resume_service import resume_service

router = APIRouter(prefix="/api/resume", tags=["Resume"])


@router.post("/upload", response_model=Dict[str, Any])
@router.post("/screen", response_model=Dict[str, Any])
async def upload_or_screen_resume(
    job_id: str = Form(...),
    file: Optional[UploadFile] = File(None),
    resume: Optional[UploadFile] = File(None),
    candidate_name: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Upload resume (PDF/DOCX), parse sections/skills, and evaluate candidate fit."""
    actual_file = file or resume
    if actual_file is None:
        raise HTTPException(
            status_code=400,
            detail="No resume file uploaded. Please upload a file via 'file' or 'resume' field.",
        )

    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    # Validate file type
    filename = actual_file.filename or "resume.pdf"
    fn_lower = filename.lower()
    if not (fn_lower.endswith(".pdf") or fn_lower.endswith(".docx") or fn_lower.endswith(".txt")):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Please upload a PDF or DOCX resume.",
        )

    # Read bytes and validate size (Max 10 MB)
    MAX_RESUME_SIZE = 10 * 1024 * 1024
    file_bytes = await actual_file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(file_bytes) > MAX_RESUME_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Resume file size exceeds maximum limit of {MAX_RESUME_SIZE // (1024*1024)} MB.",
        )

    # Magic byte MIME verification
    if fn_lower.endswith(".pdf") and not file_bytes.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Corrupted or invalid PDF file header.")
    elif fn_lower.endswith(".docx") and not file_bytes.startswith(b"PK\x03\x04"):
        raise HTTPException(status_code=400, detail="Corrupted or invalid DOCX file header.")

    # Save to storage
    storage_dir = settings.STORAGE_DIR / "resumes"
    storage_dir.mkdir(parents=True, exist_ok=True)
    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    saved_path = storage_dir / f"{session_id}_{filename}"
    saved_path.write_bytes(file_bytes)

    # Parse resume
    parsed = resume_service.parse_resume(file_bytes, filename)

    # Resolve candidate name (User provided > Parsed text > Candidate)
    c_name = (candidate_name or "").strip()
    if not c_name or c_name.lower() in ("candidate", ""):
        c_name = parsed.get("candidate_name") or "Candidate"

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
        candidate_name=c_name,
        resume_filename=filename,
        resume_text=parsed.get("raw_text", ""),
        parsed_resume={
            "candidate_name": c_name,
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

    raw_fit = screening.get("fit_score", 0.0)
    fit_score_val = round(raw_fit * 100, 1) if raw_fit <= 1.0 else round(raw_fit, 1)

    matched_skills = screening.get("matched_required_skills", []) + screening.get("matched_preferred_skills", [])
    if not matched_skills and "matched_skills" in screening:
        matched_skills = screening["matched_skills"]
    missing_skills = screening.get("missing_required_skills", screening.get("missing_skills", []))

    return {
        "session_id": session_id,
        "job_id": job.id,
        "job_title": job.title,
        "company": job.company,
        "candidate_name": c_name,
        "fit_score": fit_score_val,
        "decision": screening.get("decision", screening.get("status", "PASSED")),
        "status": screening.get("status", "PASSED"),
        "skill_score": screening.get("category_scores", {}).get("skills", 0.0),
        "experience_years": parsed.get("experience_years", 0.0),
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "gaps": {
            "missing_skills": missing_skills,
        },
        "parsed_profile": {
            "candidate_name": c_name,
            "skills": parsed.get("skills", []),
            "experience_years": parsed.get("experience_years", 0.0),
            "education": parsed.get("education", {}),
        },
        "parsed_resume": {
            "candidate_name": c_name,
            "skills": parsed.get("skills", []),
            "experience_years": parsed.get("experience_years", 0.0),
            "education": parsed.get("education", {}),
        },
        "screening": screening,
    }
