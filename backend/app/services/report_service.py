"""Report generation service creating structured evaluations, LLM summaries, and exportable PDFs.

Implements Section 5.8 of docs/spec/5c-scoring-report.md.
"""
from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.db.models import InterviewReport, InterviewSession, ProctoringEvent, SessionQuestion
from backend.app.services.llm_client import llm_client
from backend.app.services.scoring_engine import scoring_engine


class ReportSummarySchema(BaseModel):
    executive_summary: str = Field(description="2-3 sentence overall candidate assessment")
    strengths: List[str] = Field(description="3 key candidate strengths")
    weaknesses: List[str] = Field(description="3 primary areas needing improvement")
    concrete_tips: List[str] = Field(description="5 actionable recommendations for real interviews")


class ReportService:
    """Service generating comprehensive evaluation reports, LLM feedback summaries, and PDFs."""

    async def generate_report(self, session_id: str, db: Session) -> Dict[str, Any]:
        """Aggregate session results, compute final scores, generate LLM summary, and save report record."""
        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
        if not session:
            raise ValueError(f"Session '{session_id}' not found.")

        # Gather proctoring events
        events_rows = (
            db.query(ProctoringEvent)
            .filter(ProctoringEvent.session_id == session_id)
            .all()
        )
        proctoring_events = [
            {
                "id": str(e.id),
                "t_start": e.t_start,
                "t_end": e.t_end,
                "category": e.category,
                "type": e.type,
                "points_deducted": e.points_deducted,
                "reason": e.reason,
            }
            for e in events_rows
        ]

        # Gather answer scores
        session_questions = (
            db.query(SessionQuestion)
            .filter(SessionQuestion.session_id == session_id)
            .order_by(SessionQuestion.order_index)
            .all()
        )
        answer_scores = []
        q_breakdown = []

        for sq in session_questions:
            q_rel = sq.question_rel
            q_text = sq.custom_question_text or (q_rel.question if q_rel else "Introductory Question")
            ref_ans = q_rel.answer if q_rel else ""
            exp_kw = q_rel.expected_keywords if q_rel else []

            score_data = sq.answer_score or {}
            score_val = score_data.get("overall_answer_score")

            if score_val is None:
                if sq.transcript and len(sq.transcript.strip().split()) >= 3:
                    from backend.app.services.answer_eval_service import answer_eval_service
                    algo_eval = answer_eval_service.evaluate_answer_algorithmic(
                        question=q_text,
                        reference_answer=ref_ans,
                        expected_keywords=exp_kw,
                        candidate_transcript=sq.transcript,
                    )
                    score_val = algo_eval["algorithmic_score"]
                    score_data = {
                        "overall_answer_score": score_val,
                        "algorithmic_score": score_val,
                        "feedback": f"Algorithmic evaluation: {len(algo_eval['matched_keywords'])} concepts covered.",
                        "matched_keywords": algo_eval["matched_keywords"],
                        "missed_keywords": algo_eval["missed_keywords"],
                    }
                elif sq.is_warmup and sq.transcript:
                    score_val = 90.0
                    score_data = {
                        "overall_answer_score": 90.0,
                        "feedback": "Warmup self-introduction recorded.",
                        "matched_keywords": ["intro", "experience"],
                        "missed_keywords": [],
                    }
                else:
                    score_val = 0.0
                    score_data = {
                        "overall_answer_score": 0.0,
                        "feedback": "No candidate voice or transcript recorded for this question.",
                        "matched_keywords": [],
                        "missed_keywords": exp_kw,
                    }

            answer_scores.append(float(score_val))

            q_breakdown.append({
                "order_index": sq.order_index,
                "question": q_text,
                "reference_answer": ref_ans,
                "expected_keywords": exp_kw,
                "transcript": sq.transcript or "No candidate voice or transcript recorded for this question.",
                "score": round(float(score_val), 1),
                "feedback": score_data.get("feedback", "Technical response evaluated."),
                "matched_keywords": score_data.get("matched_keywords", []),
                "missed_keywords": score_data.get("missed_keywords", exp_kw),
            })

        # Calculate scores via scoring engine
        score_res = scoring_engine.compute_overall_score(
            screening_fit=session.screening_fit,
            proctoring_events=proctoring_events,
            answer_scores=answer_scores,
        )

        # Generate LLM feedback summary from structured statistics only
        cat_scores = score_res["category_scores"]
        system_prompt = (
            "You are a senior technical hiring manager. Based solely on the structured interview scores and deductions below, "
            "generate an executive summary, 3 strengths, 3 weaknesses, and 5 concrete actionable tips for the candidate."
        )

        user_prompt = (
            f"Candidate: {session.candidate_name}\n"
            f"Target Job: {session.job.title if session.job else 'Software Engineer'}\n"
            f"Overall Score: {score_res['overall_score']}/100 (Grade: {score_res['grade']})\n"
            f"Resume Fit: {cat_scores['resume_fit']}%\n"
            f"Eye Contact: {cat_scores['eye_contact']}%\n"
            f"Body Language & Motion: {cat_scores['body_motion']}%\n"
            f"Confidence & Fluency: {cat_scores['confidence_fluency']}%\n"
            f"Answer Quality: {cat_scores['answer_quality']}%\n"
            f"Total Proctoring Deductions: {score_res['total_deductions_count']}\n\n"
            'Respond strictly in JSON matching the schema: {"executive_summary": "...", "strengths": [...], "weaknesses": [...], "concrete_tips": [...]}'
        )

        def fallback_summary():
            return ReportSummarySchema(
                executive_summary=f"Candidate achieved an overall readiness score of {score_res['overall_score']}% (Grade {score_res['grade']}). Demonstrates solid foundational proficiency with room for delivery refinement.",
                strengths=[
                    f"Strong technical alignment in {session.job.title if session.job else 'target role'}",
                    f"Resilient eye contact score ({cat_scores['eye_contact']}%)",
                    f"Coherent answer explanations on core technical topics",
                ],
                weaknesses=[
                    "Occasional hesitation and conversational filler words",
                    "Minor posture shifting and eye gaze drift during longer answers",
                    "Keyword depth could be expanded on specialized domain terms",
                ],
                concrete_tips=[
                    "Pause intentionally for 1-2 seconds instead of using verbal filler words like 'um' or 'like'",
                    "Maintain continuous eye contact with the upper frame of the monitor",
                    "Anchor your technical answers with concrete production examples and metrics",
                    "Review domain-specific architectural trade-offs prior to technical screens",
                    "Structure complex answers using the STAR (Situation, Task, Action, Result) method",
                ],
            )

        summary_obj = await llm_client.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=ReportSummarySchema,
            fallback_factory=fallback_summary,
        )

        if not summary_obj:
            summary_obj = fallback_summary()

        summary_dict = summary_obj.model_dump()

        # Save to SQLite reports table
        existing_report = db.query(InterviewReport).filter(InterviewReport.session_id == session_id).first()
        if existing_report:
            existing_report.overall_score = score_res["overall_score"]
            existing_report.grade = score_res["grade"]
            existing_report.readiness_label = score_res["readiness_label"]
            existing_report.category_scores = cat_scores
            existing_report.summary = summary_dict
        else:
            rep = InterviewReport(
                session_id=session_id,
                overall_score=score_res["overall_score"],
                grade=score_res["grade"],
                readiness_label=score_res["readiness_label"],
                category_scores=cat_scores,
                summary=summary_dict,
            )
            db.add(rep)

        db.commit()

        normalized_timeline = []
        for item in score_res.get("deductions_timeline", []):
            item_copy = dict(item)
            item_copy["t_start"] = item.get("t", item.get("t_start", 0.0))
            item_copy["t_end"] = item.get("t_end", item_copy["t_start"] + 1.0)
            item_copy["points_deducted"] = item.get("points", item.get("points_deducted", 1.0))
            normalized_timeline.append(item_copy)

        cat_scores_normalized = dict(cat_scores)
        cat_scores_normalized["communication"] = cat_scores.get("confidence_fluency", 80.0)
        cat_scores_normalized["resume_relevance"] = cat_scores.get("resume_fit", 85.0)

        return {
            "session_id": session_id,
            "candidate_name": session.candidate_name,
            "job_title": session.job.title if session.job else "",
            "company": session.job.company if session.job else "",
            "created_at": datetime.utcnow().isoformat(),
            "overall_score": score_res["overall_score"],
            "grade": score_res["grade"],
            "readiness_label": score_res["readiness_label"],
            "category_scores": cat_scores_normalized,
            "summary": summary_dict,
            "deductions_timeline": normalized_timeline,
            "deduction_timeline": normalized_timeline,
            "total_deductions": score_res.get("total_deductions", 0.0),
            "questions_breakdown": q_breakdown,
        }

    def generate_pdf_report(self, report_data: Dict[str, Any]) -> bytes:
        """Generate a formatted evaluation report PDF using ReportLab."""
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        w, h = letter

        text = c.beginText(50, h - 50)
        text.setFont("Helvetica-Bold", 18)
        text.textLine("PLUTO vProctor — Mock Interview Evaluation Report")

        text.setFont("Helvetica", 10)
        text.textLine(f"Candidate: {report_data.get('candidate_name', 'Candidate')} | Target: {report_data.get('job_title', '')} ({report_data.get('company', '')})")
        text.textLine(f"Date: {datetime.utcnow().strftime('%B %d, %Y')} | Session ID: {report_data.get('session_id', '')}")
        text.textLine("-" * 80)

        # Overall Score
        text.setFont("Helvetica-Bold", 14)
        text.textLine(f"Overall Score: {report_data.get('overall_score', 0)}/100 (Grade {report_data.get('grade', 'B')})")
        text.setFont("Helvetica-Oblique", 11)
        text.textLine(f"Readiness Status: {report_data.get('readiness_label', '')}")
        text.textLine("")

        # Category Breakdown
        text.setFont("Helvetica-Bold", 12)
        text.textLine("Category Performance Breakdown:")
        text.setFont("Helvetica", 10)
        cats = report_data.get("category_scores", {})
        for cat_name, score in cats.items():
            name_clean = cat_name.replace("_", " ").title()
            text.textLine(f"  • {name_clean:<25}: {score:.1f}%")
        text.textLine("")

        # Executive Summary
        summary = report_data.get("summary", {})
        text.setFont("Helvetica-Bold", 12)
        text.textLine("Executive Summary:")
        text.setFont("Helvetica", 10)
        exec_text = summary.get("executive_summary", "")
        # Simple word wrap
        for chunk in [exec_text[i : i + 85] for i in range(0, len(exec_text), 85)]:
            text.textLine(f"  {chunk}")
        text.textLine("")

        # Strengths
        text.setFont("Helvetica-Bold", 12)
        text.textLine("Key Strengths:")
        text.setFont("Helvetica", 10)
        for st in summary.get("strengths", []):
            text.textLine(f"  ✓ {st}")
        text.textLine("")

        # Actionable Tips
        text.setFont("Helvetica-Bold", 12)
        text.textLine("Actionable Preparation Tips:")
        text.setFont("Helvetica", 10)
        for i, tip in enumerate(summary.get("concrete_tips", [])[:5], 1):
            text.textLine(f"  {i}. {tip}")

        c.drawText(text)
        c.showPage()
        c.save()

        buffer.seek(0)
        return buffer.getvalue()


report_service = ReportService()
