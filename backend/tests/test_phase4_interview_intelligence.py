"""Comprehensive automated test suite for Phase 4: Interview Intelligence, AI Evaluation, and Proctoring."""
from __future__ import annotations

import io
import uuid
import pytest
from reportlab.pdfgen import canvas

from backend.app.config import settings
from backend.app.db.database import SessionLocal
from backend.app.db.models import Company, InterviewReport, InterviewRoom, InterviewSession, Job, ProctoringEvent, Question, SessionQuestion, User
from backend.app.services.answer_eval_service import answer_eval_service
from backend.app.services.interview_service import interview_service
from backend.app.services.report_service import report_service
from backend.app.services.scoring_engine import scoring_engine
from backend.app.services.security_service import hash_password


def _seed_candidate_and_job():
    db = SessionLocal()
    uid = f"usr_{uuid.uuid4().hex[:12]}"
    jid = f"job_p4_{uuid.uuid4().hex[:8]}"
    sid = f"sess_p4_{uuid.uuid4().hex[:12]}"
    try:
        user = User(
            id=uid,
            email=f"{uid}@example.com",
            password_hash=hash_password("Password123!"),
            full_name="Candidate Intelligence Test",
            role="candidate",
            is_active=True,
            email_verified=True,
        )
        db.add(user)

        job = Job(
            id=jid,
            title="Senior Distributed Systems Engineer",
            company="CloudTech",
            question_domains=["Backend"],
            required_skills=["Distributed Systems", "Raft", "Consensus", "Go"],
            min_experience_years=4,
            pass_threshold=0.65,
        )
        db.add(job)

        session = InterviewSession(
            id=sid,
            job_id=jid,
            candidate_user_id=uid,
            candidate_name="Candidate Intelligence Test",
            interview_mode="self_practice",
            screening_fit=0.88,
            interview_status="RECORDED",
        )
        db.add(session)
        db.commit()
        return uid, jid, sid
    finally:
        db.close()


def test_structured_rubric_scoring_and_keyword_provenance():
    """Verify hybrid answer evaluation produces structured rubric subscores and keyword recall."""
    import asyncio

    async def _run():
        question = "How does the Raft consensus algorithm guarantee leader election safety?"
        reference = "Raft uses randomized election timers, term numbers, and requires candidates to have up-to-date logs to receive votes."
        expected_kw = ["randomized timer", "term number", "log replication", "majority vote"]

        cand_transcript = "In Raft, leader election relies on a randomized timer so split votes are avoided. A candidate requests votes and needs a majority vote and matching term number."

        eval_result = await answer_eval_service.evaluate_answer(
            question=question,
            reference_answer=reference,
            expected_keywords=expected_kw,
            candidate_transcript=cand_transcript,
        )

        assert "overall_answer_score" in eval_result
        assert 0.0 <= eval_result["overall_answer_score"] <= 100.0
        assert "rubric_breakdown" in eval_result
        rubric = eval_result["rubric_breakdown"]
        assert "technical_accuracy" in rubric
        assert "technical_depth" in rubric
        assert "communication_clarity" in rubric
        assert "keyword_recall" in rubric

        assert rubric["keyword_recall"] > 0.0
        assert "majority vote" in eval_result["matched_keywords"] or "term number" in eval_result["matched_keywords"]
        assert eval_result["embedding_similarity"] > 0.5

    asyncio.run(_run())


def test_adaptive_rag_followup_targeting_skill_gaps():
    """Verify adaptive follow-up generation targets candidate concept omissions."""
    import asyncio

    async def _run():
        uid, jid, sid = _seed_candidate_and_job()
        db = SessionLocal()
        try:
            # Create a catalog question
            qid = f"q_{uuid.uuid4().hex[:12]}"
            db_q = Question(
                id=qid,
                question="Explain database isolation levels and write skew anomalies.",
                answer="Write skew occurs under snapshot isolation when two concurrent transactions read overlapping data and update disjoint sets violating a constraint.",
                domain="Database",
                type="explain",
                skills=["Databases", "Concurrency"],
                expected_keywords=["snapshot isolation", "serializable", "constraint", "write skew"],
            )
            db.add(db_q)
            db.commit()

            # Seed question in session
            sq = SessionQuestion(
                session_id=sid,
                question_id=qid,
                order_index=1,
                is_warmup=False,
                is_follow_up=False,
            )
            db.add(sq)
            db.commit()

            # Brief answer missing 'write skew' and 'snapshot isolation'
            brief_ans = "Database isolation levels include read uncommitted, read committed, repeatable read, and serializable to prevent dirty reads."

            followup = await interview_service.generate_rag_followup(
                session_id=sid,
                current_question_id=qid,
                transcript=brief_ans,
                db=db,
            )

            assert followup is not None
            assert followup["is_follow_up"] is True
            assert len(followup["follow_up_question"]) > 5
            # Probing should focus on missed concepts
            reason = followup.get("reason", "")
            assert "snapshot" in reason.lower() or "skew" in reason.lower() or "missing" in reason.lower() or "probing" in reason.lower()

            # Full comprehensive answer (> 125 words) should NOT trigger unnecessary follow-ups
            long_ans = " ".join(["Database isolation levels provide varying degrees of anomaly prevention."] * 25)
            long_followup = await interview_service.generate_rag_followup(
                session_id=sid,
                current_question_id=qid,
                transcript=long_ans,
                db=db,
            )
            assert long_followup is None
        finally:
            db.close()

    asyncio.run(_run())


def test_proctoring_event_correlation_and_monotonic_scoring():
    """Verify deterministic scoring engine, timeline ordering, and scrub binary search."""
    events = [
        {"id": "ev_3", "t_start": 45.2, "category": "Eye Contact", "type": "LOOK_AWAY", "points_deducted": 2.0},
        {"id": "ev_1", "t_start": 12.0, "category": "Motion", "type": "EXCESSIVE_MOTION", "points_deducted": 1.5},
        {"id": "ev_2", "t_start": 28.5, "category": "Fluency", "type": "FILLER_WORD", "points_deducted": 1.0},
        {"id": "ev_4", "t_start": 75.0, "category": "Proctoring Integrity", "type": "LOOK_AWAY", "points_deducted": 3.0},
    ]

    answer_scores = [85.0, 90.0, 80.0]
    score_out = scoring_engine.compute_overall_score(
        screening_fit=0.90,
        proctoring_events=events,
        answer_scores=answer_scores,
    )

    assert 0.0 <= score_out["overall_score"] <= 100.0
    assert score_out["grade"] in ("A", "B", "C", "D")

    timeline = score_out["deductions_timeline"]
    assert len(timeline) == 4
    # Merge sort should guarantee strictly ascending chronological order
    timestamps = [d["t"] for d in timeline]
    assert timestamps == sorted(timestamps)
    assert timeline[0]["id"] == "ev_1"
    assert timeline[1]["id"] == "ev_2"
    assert timeline[2]["id"] == "ev_3"
    assert timeline[3]["id"] == "ev_4"

    # Test binary search scrubber near t=30.0s (should find ev_2 at 28.5 within 3.0s window)
    nearby = scoring_engine.find_deductions_near_timestamp(timeline, target_timestamp=30.0, window_seconds=3.0)
    assert len(nearby) == 1
    assert nearby[0]["id"] == "ev_2"


def test_report_generation_radar_and_analytics():
    """Verify comprehensive report generation includes radar metrics and produces exportable PDF."""
    import asyncio

    async def _run():
        uid, jid, sid = _seed_candidate_and_job()
        db = SessionLocal()
        try:
            # Seed questions and events
            db.add(ProctoringEvent(session_id=sid, t_start=15.0, t_end=17.0, category="Eye Contact", type="LOOK_AWAY", points_deducted=1.5, reason="Gaze off center"))
            db.add(SessionQuestion(session_id=sid, order_index=0, is_warmup=True, transcript="Hi, I am an experienced distributed systems engineer."))
            db.add(SessionQuestion(session_id=sid, order_index=1, custom_question_text="How do you handle split brain?", transcript="We use fencing tokens and quorum leases.", answer_score={"overall_answer_score": 88.0, "rubric_breakdown": {"technical_accuracy": 90.0, "technical_depth": 85.0, "communication_clarity": 88.0, "keyword_recall": 0.8}}))
            db.commit()

            report_data = await report_service.generate_report(sid, db)

            assert report_data["session_id"] == sid
            assert report_data["overall_score"] > 0
            assert "radar_metrics" in report_data
            radar = report_data["radar_metrics"]
            assert "technical_accuracy" in radar
            assert "problem_solving_depth" in radar
            assert "communication_clarity" in radar
            assert "proctoring_integrity" in radar
            assert "role_relevance" in radar

            for key, val in radar.items():
                assert 0.0 <= val <= 100.0, f"Radar {key} out of range: {val}"

            # Test PDF generation
            pdf_bytes = report_service.generate_pdf_report(report_data)
            assert isinstance(pdf_bytes, bytes)
            assert len(pdf_bytes) > 500
            assert pdf_bytes.startswith(b"%PDF")
        finally:
            db.close()

    asyncio.run(_run())


def test_hosted_interview_evaluation_pipeline_parity():
    """Verify hosted rooms mirror evaluation report parity with self-practice mode."""
    import asyncio

    async def _run():
        uid, jid, _ = _seed_candidate_and_job()
        db = SessionLocal()
        try:
            hosted_sid = f"sess_hosted_{uuid.uuid4().hex[:12]}"
            hosted_rid = f"room_parity_{uuid.uuid4().hex[:8]}"

            session = InterviewSession(
                id=hosted_sid,
                job_id=jid,
                candidate_user_id=uid,
                candidate_name="Hosted Parity Candidate",
                interview_mode="hosted",
                room_id=hosted_rid,
                screening_fit=0.85,
                interview_status="RECORDED",
            )
            db.add(session)

            # Mirror 2 questions
            db.add(SessionQuestion(
                session_id=hosted_sid,
                order_index=1,
                custom_question_text="Explain TLS handshake.",
                transcript="TLS 1.3 performs KeyShare in the ClientHello to complete in 1 RTT.",
                answer_score={"overall_answer_score": 92.0, "rubric_breakdown": {"technical_accuracy": 95.0, "technical_depth": 90.0, "communication_clarity": 90.0, "keyword_recall": 0.9}},
            ))
            db.commit()

            report_data = await report_service.generate_report(hosted_sid, db)
            assert report_data["session_id"] == hosted_sid
            assert report_data["overall_score"] >= 80.0
            assert "radar_metrics" in report_data
            assert len(report_data["questions_breakdown"]) == 1

            db_report = db.query(InterviewReport).filter(InterviewReport.session_id == hosted_sid).first()
            assert db_report is not None
            assert db_report.overall_score == report_data["overall_score"]
        finally:
            db.close()

    asyncio.run(_run())
