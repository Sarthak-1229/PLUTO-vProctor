"""
End-of-session report builder for PLUTO vProctor (Part 5).

Single source of truth for the practice report. Combines:
  * COMPETENCE trajectory  — per-session + per-topic Elo ability, questions
    answered, final FSM phase (the CONTENT axis; the only thing scored),
  * DESCRIPTIVE delivery observations — via core.interview.delivery,
  * content-only recommendations — weakest topics + lowest-scored items,
  * an optional PDF export (fpdf2, lazy-imported) saved under REPORTS_DIR.

NO verdicts anywhere: no pass/fail, no 0-100 gauge, no emotion / nervousness /
confidence / honesty / hireability inference. Recommendations concern CONTENT
practice only; delivery is reported as observation, never as a thing to "fix".
"""
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import config
from core.interview.delivery import get_delivery_analyzer

logger = logging.getLogger(__name__)

REPORT_DISCLAIMER = (
    "This is a self-practice diagnostic, not an evaluation of hireability. It "
    "reports content correctness and descriptive delivery observations only. It "
    "makes no judgment of emotion, nervousness, confidence, honesty, or "
    "interview-readiness, and produces no pass/fail result or 0-100 score."
)

LOW_SCORE = 0.4    # a CONTENT score below this flags the item for re-practice


class ReportBuilder:
    """Builds the structured report and (optionally) renders it to PDF."""

    def build(self, session, bank) -> Dict[str, Any]:
        """Assemble the full report dict from a session + the question bank."""
        content_items: List[dict] = []
        for rec in session.answers:
            q = bank.get(rec.question_id) or {}
            entry = {
                "question_id": rec.question_id,
                "question_text": q.get("text"),
                "category": q.get("category"),
                "topic": rec.topic,
                "b_question": rec.b_question,
                "content_score": rec.content_score,
                "content_source": rec.content_source,
            }
            if rec.rubric:
                entry["covered_points"] = rec.rubric.get("covered_points")
                entry["missing_points"] = rec.rubric.get("missing_points")
                entry["dimensions"] = rec.rubric.get("dimensions")
                entry["rationale"] = rec.rubric.get("rationale")
            content_items.append(entry)

        delivery = get_delivery_analyzer().summarize_session(session.answers)

        return {
            "session_id": session.session_id,
            "status": session.status,
            "disclaimer": REPORT_DISCLAIMER,
            "competence": {
                "overall_ability_elo": session.ability,
                "topic_ability_elo": session.topic_ability,
                "seniority_declared": session.seniority,
                "target_role": session.target_role,
                "questions_answered": session.n_answered,
                "final_phase": session.fsm_phase,
            },
            "content_breakdown": content_items,
            "delivery_observations": delivery,
            "recommendations": self._recommendations(session, content_items),
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _recommendations(self, session, content_items) -> List[str]:
        """Content-only guidance. Delivery is never turned into a 'fix this'."""
        recs: List[str] = []
        if session.topic_ability:
            for topic, ability in sorted(session.topic_ability.items(),
                                         key=lambda kv: kv[1])[:2]:
                recs.append(f"Revisit '{topic}' — measured ability there was your "
                            f"lowest ({round(ability)} Elo).")
        weak = [c for c in content_items if (c.get("content_score") or 0) < LOW_SCORE]
        for c in weak[:3]:
            recs.append(f"Re-practice: {c.get('question_text')}")
            missing = c.get("missing_points")
            if missing:
                recs.append("    Focus on: " + "; ".join(missing[:3]))
        if not recs:
            recs.append("Answer more questions for tailored, content-based recommendations.")
        return recs


    @staticmethod
    def _safe(text: Any) -> str:
        """Core PDF fonts are latin-1; replace anything outside it."""
        s = "" if text is None else str(text)
        return s.encode("latin-1", "replace").decode("latin-1")

    def to_pdf(self, report: Dict[str, Any]) -> bytes:
        """Render a report dict to PDF bytes. Raises RuntimeError if fpdf2 absent."""
        try:
            from fpdf import FPDF
        except ImportError as exc:
            raise RuntimeError("PDF export needs fpdf2: pip install fpdf2") from exc

        S = self._safe
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        def line(text, h=5, size=10, style="", gray=False):
            # new_x=LMARGIN keeps the cursor at the left edge; fpdf2's default
            # (new_x=RIGHT) would leave ~0 usable width for the next multi_cell.
            pdf.set_font("Helvetica", style, size)
            if gray:
                pdf.set_text_color(120, 120, 120)
            pdf.multi_cell(0, h, S(text), new_x="LMARGIN", new_y="NEXT")
            if gray:
                pdf.set_text_color(0, 0, 0)

        comp = report.get("competence", {})
        line("PLUTO vProctor - Practice Report", h=10, size=18, style="B")
        line(f"Session {report.get('session_id', '')[:8]}  |  "
             f"Role: {comp.get('target_role', '*')}  |  "
             f"Declared seniority: {comp.get('seniority_declared', '?')}  |  "
             f"Generated {report.get('generated_at', '')}", h=5, size=9)
        pdf.ln(2)

        line(report.get("disclaimer", ""), h=4, size=8, style="I", gray=True)
        pdf.ln(3)

        line("Competence (content correctness)", h=7, size=13, style="B")
        line(f"Overall ability: {comp.get('overall_ability_elo')} Elo   |   "
             f"Questions answered: {comp.get('questions_answered')}   |   "
             f"Final phase: {comp.get('final_phase')}", h=5, size=10)
        for topic, ab in (comp.get("topic_ability_elo") or {}).items():
            line(f"   - {topic}: {ab} Elo", h=5, size=10)
        pdf.ln(2)

        line("Per-question content scores", h=7, size=13, style="B")
        for i, c in enumerate(report.get("content_breakdown", []), 1):
            score = c.get("content_score")
            score_s = f"{score:.2f}" if isinstance(score, (int, float)) else "n/a"
            line(f"{i}. [{c.get('topic')}] content {score_s} ({c.get('content_source')})",
                 h=5, size=9, style="B")
            if c.get("question_text"):
                line(f"   {c['question_text']}", h=4, size=9)
            missing = c.get("missing_points")
            if missing:
                line("   Missing: " + "; ".join(missing[:4]), h=4, size=9)
        pdf.ln(2)

        deliv = report.get("delivery_observations", {}) or {}
        sp = deliv.get("speech", {}) or {}
        bd = deliv.get("body", {}) or {}
        line("Delivery observations (descriptive only)", h=7, size=13, style="B")
        line(deliv.get("disclaimer", ""), h=4, size=8, style="I", gray=True)
        line(f"Speech: mean {sp.get('mean_words_per_minute')} wpm, "
             f"mean filler {sp.get('mean_filler_rate_per_min')}/min, "
             f"{sp.get('total_long_pauses')} long pause(s) over "
             f"{sp.get('answers_with_speech_signal')} answer(s).", h=5, size=10)
        if bd.get("answers_with_body_signal"):
            line(f"On-camera: face-present {bd.get('mean_face_present_ratio')}, "
                 f"centered {bd.get('mean_centered_ratio')}, "
                 f"mean head-motion {bd.get('mean_head_motion')} over "
                 f"{bd.get('answers_with_body_signal')} answer(s).", h=5, size=10)
        pdf.ln(2)

        line("Recommendations (content practice)", h=7, size=13, style="B")
        for rec in report.get("recommendations", []):
            line(f"- {rec}", h=5, size=10)

        return bytes(pdf.output())


    def save_pdf(self, report: Dict[str, Any], out_dir: Optional[str] = None) -> str:
        """Render + write a PDF under REPORTS_DIR (or out_dir); return its path."""
        pdf_bytes = self.to_pdf(report)
        target = Path(out_dir or getattr(config, "REPORTS_DIR", "reports"))
        target.mkdir(parents=True, exist_ok=True)
        sid = str(report.get("session_id", "session"))[:8] or "session"
        stamp = time.strftime("%Y%m%d-%H%M%S")
        path = target / f"vproctor-report-{sid}-{stamp}.pdf"
        path.write_bytes(pdf_bytes)
        logger.info("Saved practice report PDF: %s", path)
        return str(path)


# Singleton, mirroring the other interview services.
_builder_instance: Optional[ReportBuilder] = None


def get_report_builder() -> ReportBuilder:
    global _builder_instance
    if _builder_instance is None:
        _builder_instance = ReportBuilder()
    return _builder_instance
