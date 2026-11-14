"""Candidate learning roadmap, skill growth analytics, and targeted preparation recommendations."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.app.db.models import InterviewReport, InterviewSession, ProctoringEvent, SessionQuestion, User


class RoadmapService:
    """Computes candidate historical skill progression, competency mastery, and targeted study roadmaps."""

    def get_candidate_analytics(self, db: Session, user_id: str) -> Dict[str, Any]:
        """Aggregate candidate historical interview performance metrics and readiness trends."""
        sessions = (
            db.query(InterviewSession)
            .filter(InterviewSession.candidate_user_id == user_id)
            .order_by(InterviewSession.created_at.asc())
            .all()
        )

        total_sessions = len(sessions)
        if total_sessions == 0:
            return {
                "total_interviews": 0,
                "completed_interviews": 0,
                "average_score": 0.0,
                "readiness_grade": "N/A",
                "score_trend": [],
                "skill_breakdown": {},
                "total_practice_minutes": 0,
            }

        # Gather completed reports
        session_ids = [s.id for s in sessions]
        reports = (
            db.query(InterviewReport)
            .filter(InterviewReport.session_id.in_(session_ids))
            .all()
        )
        report_map = {r.session_id: r for r in reports}

        score_trend = []
        scores_list = []
        category_sums: Dict[str, List[float]] = {
            "technical_depth": [],
            "communication": [],
            "proctoring_integrity": [],
            "resume_relevance": [],
        }

        for idx, s in enumerate(sessions, start=1):
            rep = report_map.get(s.id)
            score_val = rep.overall_score if rep else 0.0
            if rep:
                scores_list.append(score_val)
                cat_sc = rep.category_scores or {}
                for k in category_sums:
                    if k in cat_sc:
                        category_sums[k].append(float(cat_sc[k]))

            score_trend.append({
                "interview_number": idx,
                "session_id": s.id,
                "date": s.created_at.strftime("%Y-%m-%d") if s.created_at else "",
                "score": score_val,
                "grade": rep.grade if rep else "PENDING",
                "mode": s.interview_mode,
            })

        avg_score = round(sum(scores_list) / max(len(scores_list), 1), 1) if scores_list else 0.0

        if avg_score >= 85:
            current_grade = "A (Interview Ready)"
        elif avg_score >= 70:
            current_grade = "B (Competitive Candidate)"
        elif avg_score >= 55:
            current_grade = "C (Developing Proficiency)"
        else:
            current_grade = "D (Foundational Prep Needed)"

        skill_averages = {
            k: round(sum(vals) / max(len(vals), 1), 1) if vals else 75.0
            for k, vals in category_sums.items()
        }

        return {
            "total_interviews": total_sessions,
            "completed_interviews": len(scores_list),
            "average_score": avg_score,
            "readiness_grade": current_grade,
            "score_trend": score_trend,
            "skill_breakdown": skill_averages,
            "total_practice_minutes": total_sessions * 15,
        }

    def generate_learning_roadmap(self, db: Session, user_id: str) -> Dict[str, Any]:
        """Generate structured personalized learning milestones, weak-spot drills, and recommendations."""
        analytics = self.get_candidate_analytics(db, user_id)
        skills = analytics["skill_breakdown"]

        # Identify lowest-scoring competency
        sorted_skills = sorted(skills.items(), key=lambda kv: kv[1])
        weakest_area = sorted_skills[0][0] if sorted_skills else "technical_depth"

        milestones = [
            {
                "id": "m1",
                "title": "Core Technical Mastery",
                "category": "technical_depth",
                "target_score": 85.0,
                "current_score": skills.get("technical_depth", 70.0),
                "status": "completed" if skills.get("technical_depth", 0) >= 85 else "in_progress",
                "action_items": [
                    "Review database indexing and transaction isolation levels",
                    "Study distributed consensus algorithms (Raft, Paxos)",
                    "Practice explaining system architecture trade-offs out loud",
                ],
            },
            {
                "id": "m2",
                "title": "Verbal Fluency & Pacing",
                "category": "communication",
                "target_score": 80.0,
                "current_score": skills.get("communication", 75.0),
                "status": "completed" if skills.get("communication", 0) >= 80 else "in_progress",
                "action_items": [
                    "Consciously replace filler words ('um', 'like') with silent 1-second pauses",
                    "Maintain steady conversational pace of 120-140 words per minute",
                    "Anchor answers with structured STAR frameworks (Situation, Task, Action, Result)",
                ],
            },
            {
                "id": "m3",
                "title": "Proctoring Poise & Eye Contact",
                "category": "proctoring_integrity",
                "target_score": 85.0,
                "current_score": skills.get("proctoring_integrity", 80.0),
                "status": "completed" if skills.get("proctoring_integrity", 0) >= 85 else "in_progress",
                "action_items": [
                    "Calibrate webcam at eye level to prevent natural downward gaze tilt",
                    "Keep hands relaxed and upper body centered within the camera bounding box",
                    "Conduct practice mock interview in strict proctoring mode",
                ],
            },
            {
                "id": "m4",
                "title": "Role & Resume Alignment",
                "category": "resume_relevance",
                "target_score": 90.0,
                "current_score": skills.get("resume_relevance", 85.0),
                "status": "completed" if skills.get("resume_relevance", 0) >= 90 else "in_progress",
                "action_items": [
                    "Update resume technical skills section with verified competencies",
                    "Review targeted job recommendations and tailor project bullet points",
                    "Prepare 2 concrete production case studies highlighting engineering impact",
                ],
            },
        ]

        completed_count = sum(1 for m in milestones if m["status"] == "completed")
        overall_progress_pct = round((completed_count / len(milestones)) * 100)

        return {
            "user_id": user_id,
            "overall_progress_pct": overall_progress_pct,
            "primary_focus_area": weakest_area.replace("_", " ").title(),
            "milestones": milestones,
            "recommended_drills": [
                {
                    "title": "Targeted Technical Deep Dive",
                    "description": "5-question drill focusing specifically on domain knowledge gaps.",
                    "estimated_time_mins": 10,
                },
                {
                    "title": "Fluency & Speech Pacing Sandbox",
                    "description": "Short spoken response exercise with live disfluency and filler word feedback.",
                    "estimated_time_mins": 5,
                },
            ],
        }


roadmap_service = RoadmapService()

