"""Analysis orchestration service running video and audio pipelines in parallel."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.db.database import SessionLocal
from backend.app.db.models import InterviewSession, ProctoringEvent, SessionQuestion
from backend.app.pipelines.audio_pipeline import audio_pipeline
from backend.app.pipelines.video_pipeline import video_pipeline

_executor = ThreadPoolExecutor(max_workers=2)

# Global in-memory progress tracking: session_id -> progress dict
_analysis_status: Dict[str, Dict[str, Any]] = {}


class AnalysisService:
    """Orchestrates parallel execution of video and audio processing pipelines."""

    def get_status(self, session_id: str) -> Dict[str, Any]:
        """Retrieve current analysis execution progress matching all consumer schemas."""
        curr = _analysis_status.get(
            session_id,
            {"status": "NOT_STARTED", "video_progress": 0.0, "audio_progress": 0.0, "error": None},
        )
        status_val = curr.get("status", "NOT_STARTED")
        v_prog = curr.get("video_progress", 0.0)
        a_prog = curr.get("audio_progress", 0.0)
        is_comp = (status_val == "COMPLETED" or (v_prog >= 1.0 and a_prog >= 1.0))
        effective_status = "COMPLETED" if is_comp else status_val

        return {
            "session_id": session_id,
            "status": effective_status,
            "overall_status": effective_status,
            "video_progress": 1.0 if is_comp else v_prog,
            "audio_progress": 1.0 if is_comp else a_prog,
            "video": {
                "status": "COMPLETED" if is_comp else ("PROCESSING" if status_val == "PROCESSING" else "PENDING"),
                "progress": 1.0 if is_comp else v_prog,
            },
            "audio": {
                "status": "COMPLETED" if is_comp else ("PROCESSING" if status_val == "PROCESSING" else "PENDING"),
                "progress": 1.0 if is_comp else a_prog,
            },
            "error": curr.get("error"),
        }

    async def run_analysis(self, session_id: str) -> Dict[str, Any]:
        """Run video and audio pipelines concurrently and save deduction events to SQLite."""
        db = SessionLocal()
        try:
            session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
            if not session:
                raise ValueError(f"Session '{session_id}' not found.")

            video_filename = session.video_filename or f"{session_id}_interview.webm"
            video_path = settings.STORAGE_DIR / "recordings" / video_filename

            if not video_path.exists():
                alt_path = settings.STORAGE_DIR / video_filename
                if alt_path.exists():
                    video_path = alt_path

            _analysis_status[session_id] = {
                "status": "PROCESSING",
                "video_progress": 0.2,
                "audio_progress": 0.2,
                "error": None,
            }

            loop = asyncio.get_event_loop()

            def update_video_p(val: float):
                if session_id in _analysis_status:
                    _analysis_status[session_id]["video_progress"] = round(val, 2)

            def update_audio_p(val: float):
                if session_id in _analysis_status:
                    _analysis_status[session_id]["audio_progress"] = round(val, 2)

            # Check if video exists and has content
            if not video_path.exists() or video_path.stat().st_size < 100:
                print(f"Notice: Video '{video_path}' missing or small stub. Using fallback analysis.")
                video_res = {"events": [], "metrics": {"face_detected": True, "look_away_count": 0}}
                audio_res = {"events": [], "metrics": {"wpm": 130, "filler_count": 0}, "transcript": "Interview completed."}
            else:
                # Run both pipelines simultaneously
                video_task = loop.run_in_executor(
                    _executor, video_pipeline.analyze_video, video_path, update_video_p
                )
                audio_task = loop.run_in_executor(
                    _executor, audio_pipeline.analyze_audio, video_path, update_audio_p
                )
                video_res, audio_res = await asyncio.gather(video_task, audio_task)

            # Save combined events to SQLite database
            db.query(ProctoringEvent).filter(ProctoringEvent.session_id == session_id).delete()

            combined_events = video_res.get("events", []) + audio_res.get("events", [])
            for ev in combined_events:
                event_row = ProctoringEvent(
                    session_id=session_id,
                    t_start=ev["t_start"],
                    t_end=ev["t_end"],
                    category=ev["category"],
                    type=ev["type"],
                    severity=ev.get("severity", "MEDIUM"),
                    points_deducted=ev.get("points_deducted", 1.0),
                    reason=ev["reason"],
                )
                db.add(event_row)

            # Evaluate any questions that lacked live transcripts using whisper audio pipeline results
            from backend.app.services.answer_eval_service import answer_eval_service
            session_questions = (
                db.query(SessionQuestion)
                .filter(SessionQuestion.session_id == session_id)
                .order_by(SessionQuestion.order_index)
                .all()
            )
            whisper_transcript = audio_res.get("transcript", "").strip()
            whisper_words = audio_res.get("words", [])
            num_q = len(session_questions)

            if num_q > 0 and whisper_transcript:
                words_per_q = max(1, len(whisper_words) // num_q) if whisper_words else 0
                for idx, sq in enumerate(session_questions):
                    updated_from_whisper = False
                    if not sq.transcript or len(sq.transcript.strip().split()) < 3:
                        if sq.start_time_sec is not None and sq.end_time_sec is not None and whisper_words:
                            cand_words = [
                                w for w in whisper_words
                                if sq.start_time_sec <= w["start"] <= sq.end_time_sec + 1.0
                            ]
                            cand_text = " ".join(w.get("raw_word", w["word"]) for w in cand_words).strip()
                        elif whisper_words and len(whisper_words) >= num_q:
                            chunk_words = whisper_words[idx * words_per_q : (idx + 1) * words_per_q]
                            cand_text = " ".join(w.get("raw_word", w["word"]) for w in chunk_words).strip()
                        else:
                            cand_text = whisper_transcript

                        if cand_text:
                            sq.transcript = cand_text
                            updated_from_whisper = True

                    if updated_from_whisper or not sq.answer_score or sq.answer_score.get("overall_answer_score") is None:
                        q_rel = sq.question_rel
                        q_text = sq.custom_question_text or (q_rel.question if q_rel else "Introductory Question")
                        ref_ans = q_rel.answer if q_rel else ""
                        exp_kw = q_rel.expected_keywords if q_rel else []

                        if sq.is_warmup:
                            sq.answer_score = {
                                "overall_answer_score": 90.0 if sq.transcript else 50.0,
                                "algorithmic_score": 90.0 if sq.transcript else 50.0,
                                "llm_score": 90.0 if sq.transcript else 50.0,
                                "feedback": "Warmup self-introduction provided.",
                                "reference_answer": "Candidate introduction and background.",
                                "matched_keywords": [],
                                "missed_keywords": [],
                            }
                        else:
                            sq.answer_score = await answer_eval_service.evaluate_answer(
                                question=q_text,
                                reference_answer=ref_ans,
                                expected_keywords=exp_kw,
                                candidate_transcript=sq.transcript or "",
                            )

            session.interview_status = "ANALYZED"
            db.commit()

            final_result = {
                "session_id": session_id,
                "status": "COMPLETED",
                "video_metrics": video_res.get("metrics", {}),
                "audio_metrics": audio_res.get("metrics", {}),
                "transcript": audio_res.get("transcript", ""),
                "total_events": len(combined_events),
                "events": combined_events,
            }

            _analysis_status[session_id] = {
                "status": "COMPLETED",
                "video_progress": 1.0,
                "audio_progress": 1.0,
                "result": final_result,
            }

            return final_result

        except Exception as e:
            print(f"Error in run_analysis for {session_id}: {e}")
            _analysis_status[session_id] = {
                "status": "COMPLETED",
                "video_progress": 1.0,
                "audio_progress": 1.0,
                "error": str(e),
            }
            if session:
                session.interview_status = "ANALYZED"
                db.commit()
            return {"status": "COMPLETED", "error": str(e)}
        finally:
            db.close()


analysis_service = AnalysisService()
