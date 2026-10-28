"""Phase D Unit Tests: Monotonic Answer Grading, Exact Score Reconstruction, and Timeline Seek."""
import pytest
from backend.app.services.answer_eval_service import answer_eval_service
from backend.app.services.scoring_engine import scoring_engine


def test_monotonic_answer_grading_sanity():
    """Verify answer grading is strictly monotonic:

    Reference > Partial > Vague > Off-topic > Empty.
    """
    question = "Explain how Kubernetes performs container orchestration and service discovery."
    reference = (
        "Kubernetes orchestrates containers across a cluster of nodes using pods, replica sets, "
        "and deployments. For service discovery, it assigns each service a stable virtual IP and DNS name "
        "via CoreDNS, automatically routing traffic to healthy container endpoints."
    )
    keywords = ["orchestration", "pods", "deployments", "cluster", "service discovery", "dns", "endpoints"]

    # 1. Full reference answer
    score_full = answer_eval_service.evaluate_answer_algorithmic(
        question, reference, keywords, reference
    )["algorithmic_score"]

    # 2. Partial correct answer
    partial_text = "Kubernetes uses pods and deployments to manage containers on a cluster, and handles DNS for discovery."
    score_partial = answer_eval_service.evaluate_answer_algorithmic(
        question, reference, keywords, partial_text
    )["algorithmic_score"]

    # 3. Vague / shallow answer
    vague_text = "It is an orchestration platform that runs containers and helps discover servers."
    score_vague = answer_eval_service.evaluate_answer_algorithmic(
        question, reference, keywords, vague_text
    )["algorithmic_score"]

    # 4. Off-topic answer (talking about something completely different)
    off_topic_text = "To make homemade sourdough bread, mix flour, water, and wild yeast starter, then let it ferment overnight."
    score_off_topic = answer_eval_service.evaluate_answer_algorithmic(
        question, reference, keywords, off_topic_text
    )["algorithmic_score"]

    # 5. Empty / negligible answer
    empty_text = ""
    score_empty = answer_eval_service.evaluate_answer_algorithmic(
        question, reference, keywords, empty_text
    )["algorithmic_score"]

    print(f"Monotonic Scores: Full={score_full}, Partial={score_partial}, Vague={score_vague}, OffTopic={score_off_topic}, Empty={score_empty}")

    assert score_full >= 85.0
    assert score_empty == 0.0
    assert score_off_topic <= 15.0
    assert score_vague < score_partial
    assert score_partial < score_full
    # Strict monotonic relationship
    assert score_full > score_partial > score_vague > score_off_topic >= score_empty


def test_score_exact_reconstruction_from_deductions():
    """Verify category scores and overall scores are exactly reconstructable from deduction rows."""
    events = [
        {"id": "d1", "category": "Eye contact", "points_deducted": 4.0, "t_start": 10.0, "type": "LOOK_DOWN", "sub_type": "down", "reason": "Glanced down"},
        {"id": "d2", "category": "Eye contact", "points_deducted": 2.0, "t_start": 20.0, "type": "LOOK_SIDE", "sub_type": "side", "reason": "Glanced side"},
        {"id": "d3", "category": "Fluency", "points_deducted": 1.5, "t_start": 15.0, "type": "FILLER_WORD", "sub_type": "hard", "reason": "Hard filler um"},
        {"id": "d4", "category": "Body language and motion", "points_deducted": 3.0, "t_start": 30.0, "type": "EXCESSIVE_MOTION", "sub_type": "motion", "reason": "Fidgeting"},
    ]
    answers = [80.0, 90.0]  # avg = 85.0

    res = scoring_engine.compute_overall_score(
        screening_fit=0.80,  # 80.0
        proctoring_events=events,
        answer_scores=answers,
    )

    cats = res["category_scores"]
    timeline = res["deductions_timeline"]

    # Verify every row has all required traceable schema fields
    for row in timeline:
        assert "id" in row
        assert "t" in row
        assert "mmss" in row
        assert "bucket" in row
        assert "type" in row
        assert "points" in row
        assert "reason" in row
        assert "evidence_ref" in row

    # Check exact arithmetic reconstruction
    # Fluency: 100 - 1.5 = 98.5
    assert cats["confidence_fluency"] == 98.5

    # Proctoring: 100 - (4.0 + 2.0 + 3.0) = 91.0
    assert cats["proctoring_integrity"] == 91.0

    # Tech depth: avg(80, 90) = 85.0
    assert cats["technical_depth"] == 85.0

    # Resume: 80.0
    assert cats["resume_fit"] == 80.0

    # Overall calculation: 0.35 * 85 + 0.25 * 98.5 + 0.25 * 91.0 + 0.15 * 80.0
    expected_overall = round(0.35 * 85.0 + 0.25 * 98.5 + 0.25 * 91.0 + 0.15 * 80.0, 1)
    assert res["overall_score"] == expected_overall


def test_timeline_seek_binary_search_precision():
    """Verify binary search locates the exact event for timeline scrubbing within 0.3s."""
    timeline = [
        {"id": "e1", "t": 5.4, "reason": "Look down at 5.4s"},
        {"id": "e2", "t": 12.8, "reason": "Filler word at 12.8s"},
        {"id": "e3", "t": 25.0, "reason": "Pause at 25.0s"},
        {"id": "e4", "t": 42.1, "reason": "Motion at 42.1s"},
    ]

    # User clicks video at 12.9s (0.1s away from e2)
    found = scoring_engine.find_deductions_near_timestamp(timeline, target_timestamp=12.9, window_seconds=0.3)
    assert len(found) >= 1
    assert found[0]["id"] == "e2"
    assert abs(found[0]["t"] - 12.9) <= 0.3
