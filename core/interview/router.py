"""
API router for PLUTO vProctor interview mode (Part 4 — wiring).

Exposes the interview flow as a FastAPI APIRouter (prefix ``/interview``) that
composes the already-built CPU/in-browser services:
  resume_parser -> question_bank.select_for_resume -> session_store ->
  adaptive engine (next_question / record_answer) -> eval_tier1 (live) ->
  judge_llm (async report-quality refine).

Design invariants carried from the plan and enforced here:
  * COMPETENCE (content score S) is the ONLY signal that drives difficulty and
    selection. DELIVERY/confidence signals are stored DESCRIPTIVELY and never
    reach the FSM/Elo path.
  * The live difficulty path uses the fast synchronous Tier-1 score so the next
    question can be served immediately. Tier-2 (LLM rubric) refines the stored
    answer record ASYNCHRONOUSLY for the report; it deliberately does NOT
    re-fold the Elo ability, keeping the live adaptation deterministic.
  * Privacy: raw audio is transcribed then deleted immediately (never
    persisted); transcript storage honours per-session consent flags.

Transport is JSON everywhere (audio/résumé bytes travel base64) so the module
needs no python-multipart and imports cleanly even when optional deps are
absent. faster-whisper is lazy-imported only when server-side STT is used.
"""
import base64
import logging
import os
import tempfile
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from core.interview.resume_parser import get_resume_parser
from core.interview.question_bank import get_question_bank
from core.interview.session_store import get_session_store
from core.interview.adaptive import get_adaptive_engine
from core.interview.eval_tier1 import get_tier1_evaluator
from core.interview.judge_llm import get_judge
from core.interview.report import get_report_builder

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interview", tags=["interview"])

# ----------------------------------------------------------------------------
# Request bodies (JSON; bytes arrive base64-encoded)
# ----------------------------------------------------------------------------
class ResumeRequest(BaseModel):
    resume_text: Optional[str] = None
    filename: Optional[str] = None          # used to pick the parser (.pdf/.docx/.txt)
    content_base64: Optional[str] = None    # raw résumé bytes, base64


class StartRequest(BaseModel):
    # Either supply a résumé (parsed here) ...
    resume_text: Optional[str] = None
    filename: Optional[str] = None
    content_base64: Optional[str] = None
    # ... or explicit fields (e.g. the user edited the parsed profile in the UI).
    skills: Optional[List[str]] = None
    target_role: Optional[str] = None
    seniority: Optional[str] = None
    limit: int = 15
    quotas: Optional[Dict[str, int]] = None
    consent: Dict[str, bool] = Field(default_factory=dict)


class AnswerRequest(BaseModel):
    session_id: str
    question_id: str
    transcript: Optional[str] = None                 # browser STT / typed answer
    delivery: Optional[Dict[str, Any]] = None        # DESCRIPTIVE browser aggregates
    audio_base64: Optional[str] = None               # fallback: server-side STT
    audio_format: str = "webm"


# ----------------------------------------------------------------------------
# Presentation helpers
# ----------------------------------------------------------------------------
# Whitelist of fields safe to send to the candidate. The answer key
# (ideal_answer_points, keywords, scoring_rubric, red_flags, irt internals) is
# deliberately NEVER serialised to the client.
_PUBLIC_Q_FIELDS = ("id", "text", "category", "subcategory", "type", "difficulty",
                    "tags", "role_fit", "expected_answer_seconds", "language")


def _public_question(q: dict) -> dict:
    out = {k: q.get(k) for k in _PUBLIC_Q_FIELDS if k in q}
    star = q.get("expected_star")
    out["expects_star"] = bool(star and star.get("required"))
    if "_selection" in q:                # adaptation trace is metadata, not answer content
        out["_selection"] = q["_selection"]
    return out


def _require_session(session_id: str):
    session = get_session_store().get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Unknown session_id: {session_id}")
    return session


def _profile_from_payload(resume_text: Optional[str], filename: Optional[str],
                          content_base64: Optional[str]):
    """Parse a résumé from inline text or base64 bytes into a ResumeProfile."""
    parser = get_resume_parser()
    if resume_text and resume_text.strip():
        return parser.parse_text(resume_text)
    if content_base64:
        suffix = os.path.splitext(filename or "")[1].lower() or ".txt"
        try:
            data = base64.b64decode(content_base64)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid base64 content: {exc}")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        try:
            tmp.write(data)
            tmp.close()
            return parser.parse_file(tmp.name)
        except (RuntimeError, ValueError) as exc:   # missing PyMuPDF/python-docx, bad format
            raise HTTPException(status_code=400, detail=str(exc))
        finally:
            try:
                os.remove(tmp.name)
            except OSError:
                pass
    raise HTTPException(status_code=400,
                        detail="Provide 'resume_text' or 'content_base64' (+ filename).")


def _transcribe_audio_b64(audio_base64: str, audio_format: str):
    """Decode base64 audio, transcribe on CPU, then DELETE the raw clip.

    Returns (transcript, descriptive_speech_signals). The recording is never
    persisted — it exists only as a temp file for the duration of transcription.
    """
    from core.interview.stt_service import get_stt_service  # lazy: loads faster-whisper
    try:
        data = base64.b64decode(audio_base64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base64 audio: {exc}")
    suffix = "." + (audio_format or "webm").lstrip(".")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(data)
        tmp.close()
        result = get_stt_service().transcribe(tmp.name)
        return result.text.strip(), dict(result.delivery.__dict__)  # DESCRIPTIVE only
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Server-side STT failed: %s", exc)
        raise HTTPException(status_code=422,
                            detail=f"Audio transcription failed ({exc}). Send 'transcript' instead.")
    finally:
        try:
            os.remove(tmp.name)      # delete-raw-audio
        except OSError:
            pass


def _tier2_refine(session_id: str, answer_index: int, question: dict,
                  answer_text: str, tier1_score: float) -> None:
    """Background task: replace the stored Tier-1 score with the LLM rubric grade.

    This refines the RECORD used by the report only. It intentionally does not
    re-run the Elo update — the live difficulty path already committed the
    Tier-1 value, and re-folding here would make ability depend on grader
    timing. If Ollama is offline / output is malformed, JudgeLLM raises and we
    silently keep the Tier-1 score.
    """
    if not (answer_text or "").strip():
        return  # non-answer: Tier-1 already scored it ~0, nothing for the LLM to grade
    try:
        grade = get_judge().grade(question, answer_text)
    except RuntimeError as exc:
        logger.warning("Tier-2 grade unavailable (session %s, idx %s): %s",
                       session_id, answer_index, exc)
        return
    session = get_session_store().get(session_id)
    if session is None or answer_index >= len(session.answers):
        return
    rec = session.answers[answer_index]
    rec.content_score = round(float(grade.content_score), 4)
    rec.content_source = "tier2_llm"
    rec.rubric = {
        "dimensions": [d.model_dump() for d in grade.dimensions],
        "covered_points": grade.covered_points,
        "missing_points": grade.missing_points,
        "red_flags": grade.red_flags,
        "rationale": grade.rationale,
        "is_non_answer": grade.is_non_answer,
        "tier1_content_score": tier1_score,     # kept for transparency
    }
    get_session_store().save(session)
    logger.info("Tier-2 refined answer %s of session %s: S %.3f -> %.3f",
                answer_index, session_id, tier1_score, rec.content_score)


# ----------------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------------
@router.post("/resume")
def parse_resume(req: ResumeRequest):
    """Parse a résumé into a profile + a preview of the candidate question pool.

    Stateless: does not create a session. The UI shows the parsed profile
    (editable) before the user commits via POST /interview/start.
    """
    profile = _profile_from_payload(req.resume_text, req.filename, req.content_base64)
    bank = get_question_bank()
    pool = bank.select_for_resume(profile.skills, target_role=profile.inferred_role, limit=15)
    return {
        "profile": profile.to_public(),
        "pool_size": len(pool),
        "pool_preview": [_public_question(q) for q in pool],
    }


@router.post("/start")
def start_interview(req: StartRequest):
    """Create an interview session and build its resume-grounded question pool."""
    bank = get_question_bank()
    profile_public = None

    if req.skills is not None or req.target_role or req.seniority:
        # Explicit fields (UI-confirmed / edited). normalize_skills is a no-op on
        # canonical slugs and maps surface terms otherwise.
        resume_tags = bank.normalize_skills(req.skills or [])
        target_role = req.target_role or "*"
        seniority = req.seniority or "mid"
    else:
        profile = _profile_from_payload(req.resume_text, req.filename, req.content_base64)
        resume_tags = profile.skills
        target_role = profile.inferred_role
        seniority = profile.inferred_seniority
        profile_public = profile.to_public()

    pool = bank.select_for_resume(resume_tags, target_role=target_role,
                                  limit=req.limit, quotas=req.quotas)
    pool_ids = [q["id"] for q in pool]

    session = get_session_store().create(
        target_role=target_role, seniority=seniority,
        resume_tags=resume_tags, pool_ids=pool_ids, consent=req.consent,
    )
    return {
        "session_id": session.session_id,
        "target_role": session.target_role,
        "seniority": session.seniority,
        "ability_seed": session.ability,
        "pool_size": len(pool_ids),
        "consent": session.consent,
        "profile": profile_public,
        "pool_preview": [_public_question(q) for q in pool],
    }


@router.get("/next")
def next_question(session_id: str):
    """Serve the next adaptively-selected question (or signal completion)."""
    session = _require_session(session_id)
    bank = get_question_bank()
    q = get_adaptive_engine().next_question(session, bank)
    get_session_store().save(session)
    if q is None:
        return {"done": True, "session_id": session_id,
                "served": len(session.asked_ids), "pool_size": len(session.pool_ids)}
    return {
        "done": False,
        "session_id": session_id,
        "question": _public_question(q),
        "progress": {"served": len(session.asked_ids), "pool_size": len(session.pool_ids)},
    }


@router.post("/answer")
def submit_answer(req: AnswerRequest, background: BackgroundTasks):
    """Grade one answer (Tier-1 now, Tier-2 async) and fold it into the session.

    Content score S drives the live adaptation; delivery signals are stored
    DESCRIPTIVELY and never touch scoring. Call GET /interview/next afterwards
    to obtain the next question.
    """
    session = _require_session(req.session_id)
    question = get_question_bank().get(req.question_id)
    if question is None:
        raise HTTPException(status_code=404, detail=f"Unknown question_id: {req.question_id}")

    transcript = (req.transcript or "").strip()
    delivery: Dict[str, Any] = {"body": req.delivery or {}, "speech": {}, "source": "browser"}

    # Server-side STT only as a fallback when the browser sent no transcript.
    if not transcript and req.audio_base64:
        if not session.consent.get("audio", True):
            raise HTTPException(status_code=403,
                                detail="Audio consent not granted for this session.")
        transcript, delivery["speech"] = _transcribe_audio_b64(req.audio_base64, req.audio_format)
        delivery["source"] = "mixed" if req.delivery else "server_stt"

    # Tier-1 (fast, synchronous) — this is what the live difficulty path uses.
    tier1 = get_tier1_evaluator().score(question, transcript)

    stored_transcript = transcript if session.consent.get("store_transcript", True) else ""
    trace = get_adaptive_engine().record_answer(
        session, question, tier1.content_score,
        content_source="tier1", delivery=delivery, transcript=stored_transcript,
    )
    answer_index = len(session.answers) - 1
    get_session_store().save(session)

    # Tier-2 refine runs after the response is sent (report-quality grade).
    background.add_task(_tier2_refine, session.session_id, answer_index,
                        dict(question), transcript, tier1.content_score)

    return {
        "session_id": session.session_id,
        "question_id": question["id"],
        "transcript_used": transcript,
        "tier1": {
            "content_score": tier1.content_score,
            "is_non_answer": tier1.is_non_answer,
            "keyword_coverage": tier1.keyword_coverage,
            "ideal_coverage": tier1.ideal_coverage,
            "matched_keywords": tier1.matched_keywords,
        },
        "adaptation": trace,              # ability/phase deltas (CONTENT-driven)
        "delivery": delivery,             # DESCRIPTIVE ONLY
        "tier2_pending": bool(transcript),
    }


@router.get("/history")
def history(session_id: str):
    """Full served-order answer log for a session (transcript + per-item scores)."""
    session = _require_session(session_id)
    bank = get_question_bank()
    items = []
    for rec in session.answers:
        q = bank.get(rec.question_id) or {}
        items.append({
            "question_id": rec.question_id,
            "question_text": q.get("text"),
            "topic": rec.topic,
            "b_question": rec.b_question,
            "content_score": rec.content_score,
            "content_source": rec.content_source,
            "fsm_phase": rec.fsm_phase,
            "delivery": rec.delivery,
            "transcript": rec.transcript,
            "asked_at": rec.asked_at,
            "answered_at": rec.answered_at,
        })
    return {
        "session_id": session_id,
        "status": session.status,
        "target_role": session.target_role,
        "seniority": session.seniority,
        "n_answered": session.n_answered,
        "answers": items,
    }


@router.get("/questions")
def list_questions(category: Optional[str] = None, limit: int = 200):
    """Browse the question bank (presentation fields only — no answer key)."""
    bank = get_question_bank()
    qs = bank.by_category(category) if category else bank.all_questions()
    qs = qs[:max(0, limit)]
    return {"count": len(qs), "questions": [_public_question(q) for q in qs]}


@router.get("/report")
def report(session_id: str):
    """Descriptive practice report: competence trajectory + delivery observations.

    Single source of truth is ``report.ReportBuilder`` — the same dict is what
    the PDF export renders. Content-only recommendations; explicit
    no-hireability / no-emotion disclaimer; delivery is DESCRIPTIVE only.
    """
    session = _require_session(session_id)
    bank = get_question_bank()
    return get_report_builder().build(session, bank)


@router.get("/report.pdf")
def report_pdf(session_id: str, save: bool = False):
    """Return the practice report as a PDF (application/pdf).

    ``save=true`` also persists a timestamped copy under REPORTS_DIR. Responds
    501 if fpdf2 is not installed, so the JSON report stays usable regardless.
    """
    session = _require_session(session_id)
    bank = get_question_bank()
    builder = get_report_builder()
    report_dict = builder.build(session, bank)
    try:
        pdf_bytes = builder.to_pdf(report_dict)
    except RuntimeError as exc:              # fpdf2 missing
        raise HTTPException(status_code=501, detail=str(exc))
    if save:
        try:
            builder.save_pdf(report_dict)
        except Exception as exc:             # non-fatal: still stream the bytes
            logger.warning("Could not persist report PDF: %s", exc)
    filename = f"vproctor-report-{session_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.delete("/session/{session_id}")
def delete_session(session_id: str):
    """Erase all stored state for a session (consent revocation / privacy)."""
    existed = get_session_store().delete(session_id)
    if not existed:
        raise HTTPException(status_code=404, detail=f"Unknown session_id: {session_id}")
    return {"deleted": True, "session_id": session_id}
