"""Interview session management, question sequencing, and RAG follow-up generation."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.db.models import InterviewSession, Job, Question, SessionQuestion
from backend.app.services.llm_client import llm_client
from backend.app.services.question_service import question_service


class FollowUpResponse(BaseModel):
    """Schema for LLM generated follow-up question."""
    has_follow_up: bool = Field(description="Whether a follow up is necessary")
    follow_up_question: str = Field(description="One concise question under 20 words")
    reason: str = Field(default="", description="Reason for follow-up")


class InterviewService:
    """Service orchestrating interview state, question delivery, and adaptive follow-ups."""

    def start_interview(self, session_id: str, db: Session) -> Dict[str, Any]:
        """Start interview session: selects time-bounded questions and populates session_questions table."""
        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
        if not session:
            raise ValueError(f"Session '{session_id}' not found.")

        job = session.job
        job_dict = {
            "required_skills": job.required_skills or [],
            "preferred_skills": job.preferred_skills or [],
            "min_experience_years": job.min_experience_years,
            "education_levels": job.education_levels or [],
            "question_domains": job.question_domains or [],
            "pass_threshold": job.pass_threshold,
            "skill_weights": job.skill_weights or {},
        }

        parsed_resume = session.parsed_resume or {}

        # Run question selection pipeline (Knapsack ~ 12 min envelope)
        selected_questions = question_service.select_questions(
            job_dict=job_dict,
            parsed_resume=parsed_resume,
            target_duration_seconds=720,
        )

        # Remove existing questions if session restarted
        db.query(SessionQuestion).filter(SessionQuestion.session_id == session_id).delete()
        db.commit()

        # Save questions into session_questions
        sq_records = []
        for idx, q in enumerate(selected_questions):
            is_warmup = q.get("is_warmup", False)
            sq = SessionQuestion(
                session_id=session_id,
                question_id=None if is_warmup else q["id"],
                order_index=idx,
                is_warmup=is_warmup,
                is_follow_up=False,
                custom_question_text=q["question"] if is_warmup else None,
            )
            db.add(sq)
            sq_records.append(sq)

        session.interview_status = "IN_PROGRESS"
        db.commit()

        # Build response question list
        out_questions = []
        for idx, q in enumerate(selected_questions):
            out_questions.append({
                "order_index": idx,
                "question_id": q["id"],
                "question": q["question"],
                "type": q.get("type", "explain"),
                "is_warmup": q.get("is_warmup", False),
                "est_seconds": q.get("est_seconds", 70),
                "domain": q.get("domain", "General"),
                "difficulty": q.get("difficulty", 1),
                "expected_keywords": q.get("expected_keywords", []),
            })

        return {
            "session_id": session_id,
            "job_title": job.title,
            "company": job.company,
            "candidate_name": session.candidate_name,
            "total_questions": len(out_questions),
            "questions": out_questions,
        }

    async def generate_rag_followup(
        self,
        session_id: str,
        current_question_id: str,
        transcript: str,
        db: Session,
    ) -> Optional[Dict[str, Any]]:
        """Generate one short adaptive follow-up grounded in 2 nearest dataset Q&A pairs (max 3 per interview)."""
        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
        if not session:
            return None

        # Check existing follow-ups count for this session
        existing_followups = (
            db.query(SessionQuestion)
            .filter(SessionQuestion.session_id == session_id, SessionQuestion.is_follow_up.is_(True))
            .count()
        )
        if existing_followups >= 3:
            return None  # Capped at 3 follow-ups per interview session

        # Retrieve current question details
        curr_q = question_service.questions_by_id.get(current_question_id)
        if not curr_q:
            return None

        # If transcript is very detailed (> 120 words), candidate gave a full answer; no follow-up needed
        word_count = len(transcript.split())
        if word_count > 120 or word_count < 3:
            return None

        # Retrieve 2 nearest dataset Q&A pairs via cosine kNN
        nearest_neighbors = question_service.find_nearest_neighbors(curr_q["question"] + " " + transcript, k=2)
        grounding_context = "\n".join(
            [f"- Related Q: {nn['question']}\n  Expected: {nn['answer']}" for nn in nearest_neighbors]
        )

        system_prompt = (
            "You are an expert technical interviewer. The candidate just gave a brief answer. "
            "Based on the original question and the grounded domain context below, formulate ONE concise follow-up question "
            "(maximum 20 words) to test deeper understanding. If the answer is already sufficient, set has_follow_up to false."
        )

        user_prompt = (
            f"Original Question: {curr_q['question']}\n"
            f"Candidate Answer: {transcript}\n\n"
            f"Domain Reference Knowledge:\n{grounding_context}\n\n"
            'Respond in JSON: {"has_follow_up": true/false, "follow_up_question": "...", "reason": "..."}'
        )

        def fallback():
            # Deterministic fallback
            return FollowUpResponse(
                has_follow_up=False,
                follow_up_question="",
                reason="Fallback: No follow-up needed.",
            )

        result: Optional[FollowUpResponse] = await llm_client.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=FollowUpResponse,
            fallback_factory=fallback,
        )

        if result and result.has_follow_up and result.follow_up_question.strip():
            # Add follow-up question to database session
            max_order = (
                db.query(SessionQuestion.order_index)
                .filter(SessionQuestion.session_id == session_id)
                .order_by(SessionQuestion.order_index.desc())
                .first()
            )
            next_idx = (max_order[0] + 1) if max_order else 100

            sq_followup = SessionQuestion(
                session_id=session_id,
                question_id=current_question_id,
                order_index=next_idx,
                is_warmup=False,
                is_follow_up=True,
                custom_question_text=result.follow_up_question.strip(),
            )
            db.add(sq_followup)
            db.commit()

            return {
                "is_follow_up": True,
                "follow_up_question": result.follow_up_question.strip(),
                "reason": result.reason,
            }

        return None


interview_service = InterviewService()
