"""Tests for scoring engine, answer evaluation service, and report endpoints."""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.answer_eval_service import answer_eval_service
from backend.app.services.scoring_engine import scoring_engine

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
client = TestClient(app)


def test_scoring_engine_overall_score():
    """Verify scoring engine weighted category calculation and grade bands."""
    events = [
        {"category": "Eye contact", "points_deducted": 4.0, "t_start": 12.5, "reason": "Look away"},
        {"category": "Confidence (fluency)", "points_deducted": 2.5, "t_start": 5.0, "reason": "Fillers"},
        {"category": "Body language and motion", "points_deducted": 3.0, "t_start": 25.0, "reason": "Motion"},
    ]
    answer_scores = [85.0, 90.0, 80.0]

    result = scoring_engine.compute_overall_score(
        screening_fit=0.85,
        proctoring_events=events,
        answer_scores=answer_scores,
    )

    assert result["overall_score"] > 80.0
    assert result["grade"] in ["A", "B"]
    cats = result["category_scores"]
    assert cats["resume_fit"] == 85.0
    assert cats["eye_contact"] == 96.0  # 100 - 4
    assert cats["body_motion"] == 97.0  # 100 - 3
    assert cats["confidence_fluency"] == 97.5  # 100 - 2.5
    assert cats["answer_quality"] == 85.0

    # Verify deductions timeline is sorted chronologically by t
    timeline = result["deductions_timeline"]
    assert len(timeline) == 3
    assert timeline[0]["t"] <= timeline[1]["t"] <= timeline[2]["t"]
    assert timeline[0]["t"] == 5.0


def test_scoring_engine_binary_search_deductions():
    """Verify binary search locates deductions occurring near a scrubbed timestamp."""
    timeline = [
        {"t": 10.0, "reason": "A"},
        {"t": 20.0, "reason": "B"},
        {"t": 22.0, "reason": "C"},
        {"t": 35.0, "reason": "D"},
    ]
    # Scrub at t=21.0 with window 3.0s (finds 20.0 and 22.0)
    near = scoring_engine.find_deductions_near_timestamp(timeline, target_timestamp=21.0, window_seconds=3.0)
    assert len(near) == 2
    reasons = [d["reason"] for d in near]
    assert "B" in reasons and "C" in reasons


def test_answer_eval_algorithmic():
    """Verify algorithmic answer scoring extracts keyword recall and embedding similarity."""
    q = "What is a Canary Deployment?"
    ref = "New versions are released to a small subset of users first to validate performance before a full rollout."
    kw = ["canary", "users", "performance", "rollout", "validation"]
    cand = "Canary deployment is releasing software to a small group of users to test performance before rolling out to everyone."

    eval_res = answer_eval_service.evaluate_answer_algorithmic(
        question=q,
        reference_answer=ref,
        expected_keywords=kw,
        candidate_transcript=cand,
    )

    assert eval_res["algorithmic_score"] >= 70.0
    assert eval_res["keyword_recall"] >= 0.60
    assert len(eval_res["matched_keywords"]) >= 3


def test_report_endpoints():
    """Verify GET /api/report/{sid} and GET /api/report/{sid}/pdf."""
    # Create a session via resume upload
    pdf_path = FIXTURES_DIR / "resume_senior_sec_analyst.pdf"
    with open(pdf_path, "rb") as f:
        up_res = client.post(
            "/api/resume/upload",
            data={"job_id": "job_sec_analyst"},
            files={"file": (pdf_path.name, f, "application/pdf")},
        )
    session_id = up_res.json()["session_id"]

    # Start session
    client.post(f"/api/interview/{session_id}/start")

    # Fetch report JSON
    rep_res = client.get(f"/api/report/{session_id}")
    assert rep_res.status_code == 200
    rep_data = rep_res.json()
    assert rep_data["session_id"] == session_id
    assert "overall_score" in rep_data
    assert "category_scores" in rep_data
    assert "summary" in rep_data
    assert len(rep_data["summary"]["concrete_tips"]) >= 3

    # Fetch PDF download
    pdf_res = client.get(f"/api/report/{session_id}/pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert len(pdf_res.content) > 1000
