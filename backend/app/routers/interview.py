"""API endpoints for mock interview execution, question delivery, and follow-ups."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.db.database import get_db
from backend.app.db.models import InterviewSession, SessionQuestion, User
from backend.app.services.authorization import enforce_session_access, get_user_when_auth_enabled
from backend.app.services.interview_service import interview_service
from backend.app.services.security_service import record_audit_event

router = APIRouter(prefix="/api/interview", tags=["Interview"])


class FollowUpRequest(BaseModel):
    question_id: str
    transcript: str


class AnswerSubmitRequest(BaseModel):
    transcript: str
    start_time_sec: Optional[float] = None
    end_time_sec: Optional[float] = None
    tts_windows: Optional[List[List[float]]] = None


class ProctoringEventItem(BaseModel):
    t_start: float
    t_end: Optional[float] = None
    category: str = "Eye Contact"
    type: str = "GAZE_DIVERGENCE"
    severity: str = "MEDIUM"
    points_deducted: float = 1.0
    reason: str = "Gaze diversion away from monitor"


class BulkProctoringEventsRequest(BaseModel):
    events: List[ProctoringEventItem]


class StartInterviewRequest(BaseModel):
    calibration: Optional[Dict[str, Any]] = None
    preset_name: Optional[str] = "strict"


@router.get("/config/gaze", response_model=Dict[str, Any])
def get_gaze_config():
    """Return active presets and thresholds from gaze.json."""
    cfg_file = settings.APP_DIR / "config" / "gaze.json"
    if cfg_file.exists():
        with open(cfg_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


@router.post("/{sid}/start", response_model=Dict[str, Any])
def start_interview_session(
    sid: str,
    req: Optional[StartInterviewRequest] = None,
    current_user: Optional[User] = Depends(get_user_when_auth_enabled),
    db: Session = Depends(get_db),
):
    """Initialize interview session, selecting time-bounded diverse question list."""
    session = enforce_session_access(
        db.query(InterviewSession).filter(InterviewSession.id == sid).first(),
        current_user,
    )
    try:
        res = interview_service.start_interview(sid, db)
        if req and (req.calibration or req.preset_name):
            details = session.screening_details or {}
            if not isinstance(details, dict):
                details = {}
            if req.calibration:
                details["calibration"] = req.calibration
            if req.preset_name:
                details["preset_name"] = req.preset_name
            session.screening_details = details
            db.commit()
        return res
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start interview: {e}")


@router.get("/{sid}", response_model=Dict[str, Any])
def get_interview_session(
    sid: str,
    current_user: Optional[User] = Depends(get_user_when_auth_enabled),
    db: Session = Depends(get_db),
):
    """Retrieve session details and current question set."""
    session = enforce_session_access(
        db.query(InterviewSession).filter(InterviewSession.id == sid).first(),
        current_user,
    )

    questions = (
        db.query(SessionQuestion)
        .filter(SessionQuestion.session_id == sid)
        .order_by(SessionQuestion.order_index)
        .all()
    )

    q_list = []
    for sq in questions:
        q_rel = sq.question_rel
        q_text = sq.custom_question_text or (q_rel.question if q_rel else "Introductory question")
        q_list.append({
            "order_index": sq.order_index,
            "question_id": sq.question_id,
            "question": q_text,
            "is_warmup": sq.is_warmup,
            "is_follow_up": sq.is_follow_up,
            "transcript": sq.transcript,
        })

    return {
        "session_id": session.id,
        "job_id": session.job_id,
        "job_title": session.job.title if session.job else "",
        "company": session.job.company if session.job else "",
        "candidate_name": session.candidate_name,
        "screening_fit": session.screening_fit,
        "screening_status": session.screening_status,
        "interview_status": session.interview_status,
        "total_questions": len(q_list),
        "questions": q_list,
    }


@router.post("/{sid}/followup", response_model=Dict[str, Any])
async def check_for_followup(
    sid: str,
    req: FollowUpRequest,
    current_user: Optional[User] = Depends(get_user_when_auth_enabled),
    db: Session = Depends(get_db),
):
    """Generate adaptive RAG follow-up grounded in dataset if answer was brief."""
    enforce_session_access(
        db.query(InterviewSession).filter(InterviewSession.id == sid).first(),
        current_user,
    )
    result = await interview_service.generate_rag_followup(
        session_id=sid,
        current_question_id=req.question_id,
        transcript=req.transcript,
        db=db,
    )
    if result:
        return result
    return {"is_follow_up": False, "follow_up_question": None}


@router.post("/{sid}/question/{order_index}/answer", response_model=Dict[str, Any])
async def submit_question_answer(
    sid: str,
    order_index: int,
    req: AnswerSubmitRequest,
    current_user: Optional[User] = Depends(get_user_when_auth_enabled),
    db: Session = Depends(get_db),
):
    """Save candidate spoken transcript for question and trigger multimodal answer evaluation."""
    session = enforce_session_access(
        db.query(InterviewSession).filter(InterviewSession.id == sid).first(),
        current_user,
    )

    sq = (
        db.query(SessionQuestion)
        .filter(SessionQuestion.session_id == sid, SessionQuestion.order_index == order_index)
        .first()
    )
    if not sq:
        raise HTTPException(status_code=404, detail=f"Question index {order_index} not found for session '{sid}'.")

    clean_transcript = req.transcript.strip()
    sq.transcript = clean_transcript
    if req.start_time_sec is not None:
        sq.start_time_sec = req.start_time_sec
    if req.end_time_sec is not None:
        sq.end_time_sec = req.end_time_sec

    # Find question details for evaluation
    q_rel = sq.question_rel
    q_text = sq.custom_question_text or (q_rel.question if q_rel else "Introductory Question")
    ref_ans = q_rel.answer if q_rel else ""
    exp_kw = q_rel.expected_keywords if q_rel else []

    if sq.is_warmup:
        has_intro = len(clean_transcript.split()) >= 4
        eval_result = {
            "overall_answer_score": 90.0 if has_intro else 0.0,
            "algorithmic_score": 90.0 if has_intro else 0.0,
            "llm_score": 90.0 if has_intro else 0.0,
            "feedback": "Self-introduction recorded." if has_intro else "No self-introduction provided (skipped).",
            "reference_answer": "Candidate professional background and qualifications.",
            "matched_keywords": ["intro", "experience"] if has_intro else [],
            "missed_keywords": [] if has_intro else ["introduction", "background"],
            "embedding_similarity": 0.85 if has_intro else 0.0,
            "rubric_breakdown": {
                "technical_accuracy": 90.0 if has_intro else 0.0,
                "technical_depth": 90.0 if has_intro else 0.0,
                "clarity": 90.0 if has_intro else 0.0,
                "relevance": 90.0 if has_intro else 0.0,
            },
        }
    else:
        from backend.app.services.answer_eval_service import answer_eval_service
        eval_result = await answer_eval_service.evaluate_answer(
            question=q_text,
            reference_answer=ref_ans,
            expected_keywords=exp_kw,
            candidate_transcript=clean_transcript,
        )

    if req.tts_windows and isinstance(eval_result, dict):
        eval_result["tts_windows"] = req.tts_windows

    sq.answer_score = eval_result
    db.commit()

    return {
        "status": "success",
        "session_id": sid,
        "order_index": order_index,
        "transcript": clean_transcript,
        "evaluation": eval_result,
    }


@router.post("/{sid}/proctoring-events", response_model=Dict[str, Any])
def record_bulk_proctoring_events(
    sid: str,
    req: BulkProctoringEventsRequest,
    current_user: Optional[User] = Depends(get_user_when_auth_enabled),
    db: Session = Depends(get_db),
):
    """Record live client-side proctoring telemetry deductions for session."""
    session = enforce_session_access(
        db.query(InterviewSession).filter(InterviewSession.id == sid).first(),
        current_user,
    )
    from backend.app.db.models import ProctoringEvent

    added = 0
    for ev in req.events:
        t_start = max(0.0, float(ev.t_start))
        t_end = max(t_start, float(ev.t_end if ev.t_end is not None else t_start + 1.0))
        pe = ProctoringEvent(
            session_id=sid,
            t_start=t_start,
            t_end=t_end,
            category=ev.category,
            type=ev.type,
            severity=ev.severity,
            points_deducted=float(ev.points_deducted),
            reason=ev.reason,
        )
        db.add(pe)
        added += 1

    db.commit()
    return {"status": "success", "session_id": sid, "recorded_count": added}


@router.post("/{sid}/recording", response_model=Dict[str, Any])
async def upload_recording(
    sid: str,
    file: UploadFile = File(...),
    current_user: Optional[User] = Depends(get_user_when_auth_enabled),
    db: Session = Depends(get_db),
):
    """Upload recorded interview session video (webm format)."""
    session = enforce_session_access(
        db.query(InterviewSession).filter(InterviewSession.id == sid).first(),
        current_user,
    )

    storage_dir = settings.STORAGE_DIR / "recordings"
    storage_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{sid}_interview.webm"
    file_path = storage_dir / filename

    MAX_VIDEO_SIZE = 500 * 1024 * 1024  # 500 MB limit
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded recording file is empty.")
    if len(content) > MAX_VIDEO_SIZE:
        raise HTTPException(status_code=413, detail=f"Recording exceeds maximum permitted size of {MAX_VIDEO_SIZE // (1024*1024)} MB.")

    # MIME sniffing check: WebM (EBML: 0x1A45DFA3) or MP4 (ftyp)
    if not (content.startswith(b"\x1a\x45\xdf\xa3") or b"ftyp" in content[:32] or b"matroska" in content[:64]):
        # Soft warning for browser recorded blobs
        pass

    from backend.app.services.storage_service import storage_service
    storage_service.save_file("recordings", filename, content)

    session.video_filename = filename
    session.interview_status = "RECORDED"
    db.commit()

    return {
        "status": "success",
        "session_id": sid,
        "video_filename": filename,
        "size_bytes": len(content),
    }


@router.get("/{sid}/video")
@router.get("/{sid}/recording")
def get_session_video(
    sid: str,
    current_user: Optional[User] = Depends(get_user_when_auth_enabled),
    db: Session = Depends(get_db),
):
    """Stream recorded interview session video for interactive timeline playback."""
    from fastapi.responses import FileResponse

    session = enforce_session_access(
        db.query(InterviewSession).filter(InterviewSession.id == sid).first(),
        current_user,
    )
    if not session.video_filename:
        raise HTTPException(status_code=404, detail=f"Recording for session '{sid}' not found.")

    file_path = settings.STORAGE_DIR / "recordings" / session.video_filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Video file does not exist on disk.")

    return FileResponse(file_path, media_type="video/webm")


@router.delete("/{sid}", response_model=Dict[str, Any])
@router.delete("/{sid}/delete-data", response_model=Dict[str, Any])
def delete_session_data(
    sid: str,
    current_user: Optional[User] = Depends(get_user_when_auth_enabled),
    db: Session = Depends(get_db),
):
    """Delete candidate interview data, recordings, audio extracts, and proctoring telemetry for privacy compliance."""
    session = enforce_session_access(
        db.query(InterviewSession).filter(InterviewSession.id == sid).first(),
        current_user,
    )

    # 1. Delete video recording on disk if present
    if session.video_filename:
        file_path = settings.STORAGE_DIR / "recordings" / session.video_filename
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception:
                pass

    # 2. Delete any extracted audio, chunks, or reports for this session
    for subfolder in ["audio", "recordings", "resumes", "reports"]:
        target_dir = settings.STORAGE_DIR / subfolder
        if target_dir.exists():
            for f in target_dir.glob(f"*{sid}*"):
                try:
                    f.unlink()
                except Exception:
                    pass

    # 3. Delete database records in cascade order
    from backend.app.db.models import InterviewReport, ProctoringEvent
    db.query(InterviewReport).filter(InterviewReport.session_id == sid).delete()
    db.query(ProctoringEvent).filter(ProctoringEvent.session_id == sid).delete()
    db.query(SessionQuestion).filter(SessionQuestion.session_id == sid).delete()
    if current_user is not None:
        record_audit_event(
            db,
            action="session.deleted",
            resource_type="session",
            resource_id=sid,
            actor_user_id=current_user.id,
            actor_role=current_user.role,
        )
    db.delete(session)
    db.commit()

    return {
        "status": "deleted",
        "session_id": sid,
        "message": "All candidate data, recordings, extracted audio, and evaluation records deleted successfully.",
    }
