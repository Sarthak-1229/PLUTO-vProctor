"""Deterministic scoring engine combining deductions across all proctoring categories.

Implements Section 5.6 of docs/spec/5c-scoring-report.md:
- Resume Fit: 20%
- Eye Contact: 20%
- Body Language & Motion: 15%
- Confidence & Fluency: 25%
- Answer Quality: 20%
Deductions ordered via hand-implemented Merge Sort and binary-searchable by timestamp.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from backend.app.algorithms.searching import find_closest_timestamp, lower_bound, upper_bound
from backend.app.algorithms.sorting import merge_sort


def format_seconds_mmss(seconds: float) -> str:
    """Format seconds float into mm:ss timestamp string."""
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"


class ScoringEngine:
    """Calculates overall scores, category grades, and timeline deductions."""

    CATEGORY_WEIGHTS = {
        "resume_fit": 0.20,
        "eye_contact": 0.20,
        "body_motion": 0.15,
        "confidence_fluency": 0.25,
        "answer_quality": 0.20,
    }

    def compute_overall_score(
        self,
        screening_fit: float,
        proctoring_events: List[Dict[str, Any]],
        answer_scores: List[float],
    ) -> Dict[str, Any]:
        """Combine all category deductions and compute weighted overall score and grade band."""
        # Category starting points (100 each)
        cat_scores = {
            "resume_fit": round(screening_fit * 100.0, 1),
            "eye_contact": 100.0,
            "body_motion": 100.0,
            "confidence_fluency": 100.0,
            "answer_quality": 100.0,
        }

        # Apply deductions from proctoring events
        formatted_deductions = []

        for ev in proctoring_events:
            cat = ev.get("category", "")
            pts = float(ev.get("points_deducted", 1.0))
            t_start = float(ev.get("t_start", 0.0))

            if "eye" in cat.lower():
                cat_scores["eye_contact"] -= pts
            elif "body" in cat.lower() or "motion" in cat.lower():
                cat_scores["body_motion"] -= pts
            elif "confidence" in cat.lower() or "fluency" in cat.lower():
                cat_scores["confidence_fluency"] -= pts

            formatted_deductions.append({
                "id": ev.get("id", f"ded_{len(formatted_deductions)}"),
                "t": t_start,
                "mmss": format_seconds_mmss(t_start),
                "category": cat,
                "type": ev.get("type", "VIOLATION"),
                "points": pts,
                "reason": ev.get("reason", "Proctoring violation"),
                "question_id": ev.get("question_id"),
            })

        # Answer Quality score
        if answer_scores:
            cat_scores["answer_quality"] = round(sum(answer_scores) / len(answer_scores), 1)

        # Clamp all categories to [0, 100]
        for k in cat_scores:
            cat_scores[k] = round(max(0.0, min(100.0, cat_scores[k])), 1)

        # Compute weighted overall score
        overall = sum(
            cat_scores[cat] * self.CATEGORY_WEIGHTS[cat] for cat in self.CATEGORY_WEIGHTS
        )
        overall_score = round(max(0.0, min(100.0, overall)), 1)

        # Grade Band and Readiness
        if overall_score >= 85.0:
            grade = "A"
            readiness = "Interview Ready (Strong Recommendation)"
        elif overall_score >= 70.0:
            grade = "B"
            readiness = "Ready with Minor Polish"
        elif overall_score >= 55.0:
            grade = "C"
            readiness = "Needs Practice Before Real Interview"
        else:
            grade = "D"
            readiness = "Requires Substantial Preparation"

        # Chronologically sort deductions using custom merge sort
        sorted_deductions = merge_sort(formatted_deductions, key=lambda d: d["t"])

        return {
            "overall_score": overall_score,
            "grade": grade,
            "readiness_label": readiness,
            "category_scores": cat_scores,
            "deductions_timeline": sorted_deductions,
            "total_deductions_count": len(sorted_deductions),
        }

    def find_deductions_near_timestamp(
        self,
        sorted_deductions: List[Dict[str, Any]],
        target_timestamp: float,
        window_seconds: float = 3.0,
    ) -> List[Dict[str, Any]]:
        """Search deductions occurring near a video scrub timestamp using custom binary search."""
        if not sorted_deductions:
            return []

        timestamps = [d["t"] for d in sorted_deductions]
        start_t = max(0.0, target_timestamp - window_seconds)
        end_t = target_timestamp + window_seconds

        left = lower_bound(timestamps, start_t)
        right = upper_bound(timestamps, end_t)
        return sorted_deductions[left:right]


scoring_engine = ScoringEngine()
