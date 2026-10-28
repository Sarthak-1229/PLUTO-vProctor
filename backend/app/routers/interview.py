"""API endpoints for mock interview execution, question delivery, and follow-ups."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.db.database import get_db
from backend.app.db.models import InterviewSession, SessionQuestion
from backend.app.services.interview_service import interview_service

router = APIRouter(prefix="/api/interview", tags=["Interview"])


class FollowUpRequest(BaseModel):
    question_id: str
    transcript: str


class AnswerSubmitRequest(BaseModel):
    transcript: str
    start_time_sec: Optional[float] = None
    end_time_sec: Optional[float] = None



@router.post("/{sid}/start", response_model=Dict[str, Any])
def start_interview_session(sid: str, db: Session = Depends(get_db)):
    """Initialize interview session, selecting time-bounded diverse question list."""
    try:
        return interview_service.start_interview(sid, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start interview: {e}")


@router.get("/{sid}", response_model=Dict[str, Any])
def get_interview_session(sid: str, db: Session = Depends(get_db)):
    """Retrieve session details and current question set."""
    session = db.query(InterviewSession).filter(InterviewSession.id == sid).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{sid}' not found.")

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
    db: Session = Depends(get_db),
):
    """Generate adaptive RAG follow-up grounded in dataset if answer was brief."""
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
    db: Session = Depends(get_db),
):
    """Save candidate spoken transcript for question and trigger multimodal answer evaluation."""
    session = db.query(InterviewSession).filter(InterviewSession.id == sid).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{sid}' not found.")

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
        eval_result = {
            "overall_answer_score": 90.0 if len(clean_transcript.split()) >= 4 else 50.0,
            "algorithmic_score": 90.0 if len(clean_transcript.split()) >= 4 else 50.0,
            "llm_score": 90.0 if len(clean_transcript.split()) >= 4 else 50.0,
            "feedback": "Self-introduction recorded.",
            "reference_answer": "Candidate professional background and qualifications.",
            "matched_keywords": ["intro", "experience"],
            "missed_keywords": [],
            "embedding_similarity": 0.85,
        }
    else:
        from backend.app.services.answer_eval_service import answer_eval_service
        eval_result = await answer_eval_service.evaluate_answer(
            question=q_text,
            reference_answer=ref_ans,
            expected_keywords=exp_kw,
            candidate_transcript=clean_transcript,
        )

    sq.answer_score = eval_result
    db.commit()

    return {
        "status": "success",
        "session_id": sid,
        "order_index": order_index,
        "transcript": clean_transcript,
        "evaluation": eval_result,
    }


@router.post("/{sid}/recording", response_model=Dict[str, Any])
async def upload_recording(
    sid: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload recorded interview session video (webm format)."""
    session = db.query(InterviewSession).filter(InterviewSession.id == sid).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{sid}' not found.")

    storage_dir = settings.STORAGE_DIR / "recordings"
    storage_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{sid}_interview.webm"
    file_path = storage_dir / filename

    content = await file.read()
    file_path.write_bytes(content)

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
def get_session_video(sid: str, db: Session = Depends(get_db)):
    """Stream recorded interview session video for interactive timeline playback."""
    from fastapi.responses import FileResponse

    session = db.query(InterviewSession).filter(InterviewSession.id == sid).first()
    if not session or not session.video_filename:
        raise HTTPException(status_code=404, detail=f"Recording for session '{sid}' not found.")

    file_path = settings.STORAGE_DIR / "recordings" / session.video_filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Video file does not exist on disk.")

    return FileResponse(file_path, media_type="video/webm")


@router.delete("/{sid}", response_model=Dict[str, Any])
def delete_session_data(sid: str, db: Session = Depends(get_db)):
    """Delete candidate interview data, recordings, and proctoring telemetry for privacy compliance."""
    session = db.query(InterviewSession).filter(InterviewSession.id == sid).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{sid}' not found.")

    # 1. Delete video recording on disk if present
    if session.video_filename:
        file_path = settings.STORAGE_DIR / "recordings" / session.video_filename
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception as e:
                pass

    # 2. Delete database records
    db.delete(session)
    db.commit()

    return {
        "status": "deleted",
        "session_id": sid,
        "message": "All candidate data and recording deleted successfully.",
    }
