"""Secure candidate resume upload, validation, private storage, and editable parsed profiles."""
from __future__ import annotations

import hashlib
import io
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pdfplumber
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.core.errors import AppError
from backend.app.db.models import InterviewSession, Job, Resume, ResumeProfile, User
from backend.app.services.authorization import enforce_resume_ownership
from backend.app.services.resume_service import resume_service
from backend.app.services.security_service import record_audit_event, utcnow_naive

MAX_RESUME_BYTES = 5 * 1024 * 1024  # 5 MB hard cap for v2 candidate resume library
MAX_PDF_PAGES = 15
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
ALLOWED_CONTENT_TYPES = {
    ".pdf": {"application/pdf", "application/octet-stream"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
        "application/octet-stream",
    },
    ".txt": {"text/plain", "text/markdown", "application/octet-stream"},
}


def _resume_storage_dir() -> Path:
    d = settings.STORAGE_DIR / "resumes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _validate_and_inspect_upload(
    *,
    filename: str,
    content_type: Optional[str],
    file_bytes: bytes,
) -> tuple[str, str, str]:
    clean_name = Path(filename or "resume.pdf").name.replace("..", "_").strip() or "resume.pdf"
    ext = Path(clean_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise AppError(
            status_code=400,
            code="unsupported_file_type",
            message="Unsupported resume format. Allowed types are PDF, DOCX, and TXT.",
        )

    if not file_bytes:
        raise AppError(status_code=400, code="empty_file", message="Uploaded resume file is empty.")
    if len(file_bytes) > MAX_RESUME_BYTES:
        raise AppError(
            status_code=413,
            code="file_too_large",
            message=f"Resume exceeds maximum permitted size of {MAX_RESUME_BYTES // (1024 * 1024)} MB.",
        )

    norm_ct = (content_type or "application/octet-stream").split(";")[0].strip().lower()
    if norm_ct not in ALLOWED_CONTENT_TYPES[ext]:
        raise AppError(
            status_code=400,
            code="invalid_mime_type",
            message="Uploaded file MIME type does not match its extension.",
        )

    # Strict magic-byte / structure verification
    if ext == ".pdf":
        if not file_bytes.startswith(b"%PDF-"):
            raise AppError(status_code=400, code="invalid_pdf_magic", message="Invalid or spoofed PDF file header.")
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                if len(pdf.pages) > MAX_PDF_PAGES:
                    raise AppError(
                        status_code=400,
                        code="pdf_too_many_pages",
                        message=f"PDF resume exceeds maximum limit of {MAX_PDF_PAGES} pages.",
                    )
        except AppError:
            raise
        except Exception as exc:
            raise AppError(status_code=400, code="corrupt_pdf", message="Unable to read PDF document.") from exc
        resolved_mime = "application/pdf"
    elif ext == ".docx":
        if not file_bytes.startswith(b"PK\x03\x04"):
            raise AppError(status_code=400, code="invalid_docx_magic", message="Invalid or spoofed DOCX file header.")
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                names = set(zf.namelist())
                if "word/document.xml" not in names:
                    raise AppError(status_code=400, code="invalid_docx_structure", message="Invalid DOCX archive structure.")
        except AppError:
            raise
        except Exception as exc:
            raise AppError(status_code=400, code="corrupt_docx", message="Corrupted DOCX archive.") from exc
        resolved_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        if b"\x00" in file_bytes[:4096] or file_bytes[:2] == b"MZ" or file_bytes[:4] == b"\x7fELF":
            raise AppError(status_code=400, code="invalid_text_file", message="Binary payload rejected in TXT resume upload.")
        try:
            file_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AppError(status_code=400, code="invalid_utf8_text", message="Text resume must be UTF-8 encoded.") from exc
        resolved_mime = "text/plain"

    return clean_name[:200], ext, resolved_mime


def _build_initial_provenance(parsed: Dict[str, Any]) -> Dict[str, Any]:
    skills = parsed.get("skills") or []
    exp = float(parsed.get("experience_years") or 0.0)
    edu = parsed.get("education") or {}
    return {
        "candidate_name": {
            "source": "parsed",
            "verified": False,
            "present": bool(parsed.get("candidate_name") and parsed.get("candidate_name") != "Candidate"),
        },
        "skills": {
            "source": "parsed",
            "verified": False,
            "extracted_count": len(skills),
        },
        "experience_years": {
            "source": "parsed",
            "verified": False,
            "intervals_detected": len(parsed.get("experience_intervals") or []),
            "value": exp,
        },
        "education": {
            "source": "parsed",
            "verified": False,
            "degree_detected": edu.get("degree", "None"),
        },
    }


def _effective_resume_data(rp: ResumeProfile) -> Dict[str, Any]:
    base = dict(rp.extracted_data_json or {})
    edits = dict(rp.edited_data_json or {})
    merged = {**base, **edits}
    return merged


def serialize_resume_bundle(res: Resume, rp: Optional[ResumeProfile]) -> Dict[str, Any]:
    """Serialize resume metadata + extracted/edited/confirmed parsed fields without exposing raw disk paths."""
    profile_payload = None
    if rp is not None:
        profile_payload = {
            "id": rp.id,
            "resume_id": rp.resume_id,
            "extracted_data": rp.extracted_data_json or {},
            "edited_data": rp.edited_data_json,
            "effective_data": _effective_resume_data(rp),
            "provenance": rp.field_provenance_json or {},
            "confirmed_by_user": bool(rp.confirmed_by_user),
            "confirmed_at": rp.confirmed_at.isoformat() if rp.confirmed_at else None,
            "updated_at": rp.updated_at.isoformat() if rp.updated_at else None,
        }
    return {
        "resume": {
            "id": res.id,
            "user_id": res.user_id,
            "original_filename": res.original_filename,
            "storage_key": res.storage_key,
            "mime_type": res.mime_type,
            "file_size_bytes": res.file_size_bytes,
            "sha256_hash": res.sha256_hash,
            "is_active": bool(res.is_active),
            "created_at": res.created_at.isoformat() if res.created_at else None,
        },
        "resume_profile": profile_payload,
    }


def upload_and_parse_resume(
    db: Session,
    *,
    user: User,
    filename: str,
    content_type: Optional[str],
    file_bytes: bytes,
    ip_address: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate, store privately under random UUID key, parse, and record editable ResumeProfile."""
    clean_name, ext, resolved_mime = _validate_and_inspect_upload(
        filename=filename,
        content_type=content_type,
        file_bytes=file_bytes,
    )

    storage_dir = _resume_storage_dir().resolve()
    storage_key = f"res_{uuid.uuid4().hex}{ext}"
    dest = (storage_dir / storage_key).resolve()
    if dest.parent != storage_dir:
        raise AppError(status_code=400, code="invalid_storage_target", message="Invalid storage key.")

    dest.write_bytes(file_bytes)
    sha256_hex = hashlib.sha256(file_bytes).hexdigest()

    try:
        parsed = resume_service.parse_resume(file_bytes, clean_name)
    except Exception:
        dest.unlink(missing_ok=True)
        raise

    now = utcnow_naive()
    res = Resume(
        id=f"res_{uuid.uuid4().hex[:16]}",
        user_id=user.id,
        original_filename=clean_name,
        storage_key=storage_key,
        mime_type=resolved_mime,
        file_size_bytes=len(file_bytes),
        sha256_hash=sha256_hex,
        raw_text=parsed.get("raw_text", ""),
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(res)
    db.flush()

    extracted_summary = {
        "candidate_name": parsed.get("candidate_name") or user.full_name,
        "skills": parsed.get("skills", []),
        "experience_years": float(parsed.get("experience_years", 0.0)),
        "experience_intervals": parsed.get("experience_intervals", []),
        "education": parsed.get("education", {"degree": "None", "rank": 0, "fields": []}),
        "sections": {k: str(v)[:1000] for k, v in (parsed.get("sections") or {}).items()},
    }
    rp = ResumeProfile(
        id=f"rprof_{uuid.uuid4().hex[:16]}",
        resume_id=res.id,
        user_id=user.id,
        extracted_data_json=extracted_summary,
        edited_data_json=None,
        field_provenance_json=_build_initial_provenance(parsed),
        confirmed_by_user=False,
        created_at=now,
        updated_at=now,
    )
    db.add(rp)
    record_audit_event(
        db,
        action="resume.uploaded",
        resource_type="resume",
        resource_id=res.id,
        actor_user_id=user.id,
        actor_role=user.role,
        details={"original_filename": clean_name, "mime_type": resolved_mime, "size_bytes": len(file_bytes)},
        ip_address=ip_address,
    )
    db.commit()
    return serialize_resume_bundle(res, rp)


def list_user_resumes(db: Session, user_id: str) -> List[Dict[str, Any]]:
    rows = (
        db.query(Resume, ResumeProfile)
        .outerjoin(ResumeProfile, ResumeProfile.resume_id == Resume.id)
        .filter(Resume.user_id == user_id)
        .order_by(Resume.created_at.desc())
        .all()
    )
    return [serialize_resume_bundle(r, rp) for r, rp in rows]


def get_resume_for_user(db: Session, resume_id: str, user: User) -> Dict[str, Any]:
    res = enforce_resume_ownership(db.query(Resume).filter(Resume.id == resume_id).first(), user)
    rp = db.query(ResumeProfile).filter(ResumeProfile.resume_id == res.id).first()
    return serialize_resume_bundle(res, rp)


def update_resume_profile_fields(
    db: Session,
    *,
    resume_id: str,
    user: User,
    updates: Dict[str, Any],
    ip_address: Optional[str] = None,
) -> Dict[str, Any]:
    """Save candidate edits over extracted resume fields without mutating raw original extraction."""
    res = enforce_resume_ownership(db.query(Resume).filter(Resume.id == resume_id).first(), user)
    rp = db.query(ResumeProfile).filter(ResumeProfile.resume_id == res.id).first()
    if rp is None:
        raise AppError(status_code=404, code="resume_profile_not_found", message="Parsed resume profile not found.")

    edited = dict(rp.edited_data_json or {})
    provenance = dict(rp.field_provenance_json or {})
    now = utcnow_naive()

    for field in ("candidate_name", "skills", "experience_years", "education", "summary"):
        if field in updates and updates[field] is not None:
            val = updates[field]
            if field == "skills":
                val = list(dict.fromkeys(str(s).strip() for s in val if str(s).strip()))[:60]
            elif field == "candidate_name":
                val = str(val).strip()[:128]
            elif field == "experience_years":
                val = float(val)
            edited[field] = val
            provenance[field] = {
                **(provenance.get(field) or {}),
                "source": "manual_edit",
                "verified": True,
                "edited_at": now.isoformat(),
            }

    rp.edited_data_json = edited
    rp.field_provenance_json = provenance
    rp.updated_at = now
    record_audit_event(
        db,
        action="resume_profile.updated",
        resource_type="resume",
        resource_id=res.id,
        actor_user_id=user.id,
        actor_role=user.role,
        details={"updated_fields": sorted(k for k, v in updates.items() if v is not None)},
        ip_address=ip_address,
    )
    db.commit()
    return serialize_resume_bundle(res, rp)


def confirm_resume_profile(
    db: Session,
    *,
    resume_id: str,
    user: User,
    ip_address: Optional[str] = None,
) -> Dict[str, Any]:
    res = enforce_resume_ownership(db.query(Resume).filter(Resume.id == resume_id).first(), user)
    rp = db.query(ResumeProfile).filter(ResumeProfile.resume_id == res.id).first()
    if rp is None:
        raise AppError(status_code=404, code="resume_profile_not_found", message="Parsed resume profile not found.")

    now = utcnow_naive()
    rp.confirmed_by_user = True
    rp.confirmed_at = now
    rp.updated_at = now
    provenance = dict(rp.field_provenance_json or {})
    for k, meta in provenance.items():
        if isinstance(meta, dict):
            provenance[k] = {**meta, "verified": True}
    rp.field_provenance_json = provenance

    record_audit_event(
        db,
        action="resume_profile.confirmed",
        resource_type="resume",
        resource_id=res.id,
        actor_user_id=user.id,
        actor_role=user.role,
        ip_address=ip_address,
    )
    db.commit()
    return serialize_resume_bundle(res, rp)


def delete_resume_completely(
    db: Session,
    *,
    resume_id: str,
    user: User,
    ip_address: Optional[str] = None,
) -> None:
    """Hard-delete private stored file, parsed profile, and resume record."""
    res = enforce_resume_ownership(db.query(Resume).filter(Resume.id == resume_id).first(), user)
    disk_path = _resume_storage_dir() / res.storage_key
    if disk_path.exists():
        disk_path.unlink(missing_ok=True)

    db.query(ResumeProfile).filter(ResumeProfile.resume_id == res.id).delete()
    db.delete(res)
    record_audit_event(
        db,
        action="resume.deleted",
        resource_type="resume",
        resource_id=resume_id,
        actor_user_id=user.id,
        actor_role=user.role,
        ip_address=ip_address,
    )
    db.commit()


def create_interview_session_from_saved_resume(
    db: Session,
    *,
    resume_id: str,
    job_id: str,
    user: User,
) -> Dict[str, Any]:
    """Start a job screening + interview session directly from a candidate's saved/edited resume."""
    res = enforce_resume_ownership(db.query(Resume).filter(Resume.id == resume_id).first(), user)
    rp = db.query(ResumeProfile).filter(ResumeProfile.resume_id == res.id).first()
    job = db.query(Job).filter(Job.id == job_id).first()
    if job is None:
        raise AppError(status_code=404, code="job_not_found", message=f"Job '{job_id}' not found.")

    effective = _effective_resume_data(rp) if rp else {"candidate_name": user.full_name, "skills": [], "experience_years": 0.0, "education": {}}
    parsed_for_fit = {
        "candidate_name": effective.get("candidate_name") or user.full_name,
        "skills": effective.get("skills", []),
        "experience_years": float(effective.get("experience_years", 0.0)),
        "education": effective.get("education") or {"degree": "None", "rank": 0, "fields": []},
    }
    job_dict = {
        "required_skills": job.required_skills or [],
        "preferred_skills": job.preferred_skills or [],
        "min_experience_years": job.min_experience_years,
        "education_levels": job.education_levels or [],
        "pass_threshold": job.pass_threshold,
        "skill_weights": job.skill_weights or {},
    }
    screening = resume_service.calculate_fit(parsed_for_fit, job_dict)
    raw_fit = screening.get("fit_score", 0.0)
    fit_score_val = round(raw_fit * 100, 1) if raw_fit <= 1.0 else round(raw_fit, 1)

    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    session_obj = InterviewSession(
        id=session_id,
        job_id=job.id,
        candidate_user_id=user.id,
        candidate_name=parsed_for_fit["candidate_name"],
        resume_filename=res.original_filename,
        resume_text=res.raw_text or "",
        parsed_resume=parsed_for_fit,
        screening_fit=screening["fit_score"],
        screening_status=screening["status"],
        screening_details=screening,
        interview_status="CREATED",
        interview_mode="self_practice",
    )
    db.add(session_obj)
    db.commit()

    matched = screening.get("matched_required_skills", []) + screening.get("matched_preferred_skills", [])
    missing = screening.get("missing_required_skills", screening.get("missing_skills", []))
    return {
        "session_id": session_id,
        "job_id": job.id,
        "job_title": job.title,
        "company": job.company,
        "candidate_name": parsed_for_fit["candidate_name"],
        "fit_score": fit_score_val,
        "decision": screening.get("decision", screening.get("status", "PASSED")),
        "status": screening.get("status", "PASSED"),
        "matched_skills": matched,
        "missing_skills": missing,
        "gaps": {"missing_skills": missing},
        "parsed_profile": parsed_for_fit,
        "screening": screening,
    }

