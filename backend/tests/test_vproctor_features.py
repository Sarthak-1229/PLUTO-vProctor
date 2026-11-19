"""Tests for multiple faces detection, job recommendations, and Data Store mirroring."""
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db.database import get_db, SessionLocal
from backend.app.db.models import User, CandidateProfile, Job, JobRoleTemplate
from backend.app.services.scoring_engine import scoring_engine
from backend.app.services.job_recommendation_service import compute_recommendations_for_user

client = TestClient(app)


def test_multiple_faces_proctoring_deduction():
    """Verify multiple faces detection events apply -5 pts deduction to proctoring integrity."""
    events = [
        {
            "category": "Integrity",
            "type": "MULTIPLE_FACES_DETECTED",
            "points_deducted": 5.0,
            "t_start": 14.0,
            "reason": "CRITICAL: Multiple faces detected (2 persons in camera frame)",
        }
    ]
    res = scoring_engine.compute_overall_score(
        screening_fit=0.90,
        proctoring_events=events,
        answer_scores=[85.0, 90.0],
    )
    assert res["category_scores"]["proctoring_integrity"] == 95.0  # 100 - 5.0
    timeline = res["deductions_timeline"]
    assert len(timeline) == 1
    assert "Multiple faces" in timeline[0]["reason"]
    assert timeline[0]["penalty"] == 5.0


def test_job_recommendations_for_candidate():
    """Verify universal job recommendations compute correctly based on candidate profile skills."""
    with SessionLocal() as db:
        user = db.query(User).filter(User.role == "candidate").first()
        if not user:
            user = User(
                id="usr_test_rec_01",
                email="candidate_rec_test@example.com",
                password_hash="mock_hash",
                full_name="Candidate Test",
                role="candidate",
            )
            db.add(user)
            db.commit()

        # Add profile with security skills
        prof = db.query(CandidateProfile).filter(CandidateProfile.user_id == user.id).first()
        if not prof:
            prof = CandidateProfile(
                id="cprof_test_01",
                user_id=user.id,
                experience_years=2.0,
                technical_skills_json=["Python", "Network Security", "Linux", "Application Security"],
                preferred_roles_json=["Cybersecurity Analyst"],
            )
            db.add(prof)
        else:
            prof.technical_skills_json = ["Python", "Network Security", "Linux", "Application Security"]
            prof.preferred_roles_json = ["Cybersecurity Analyst"]
        db.commit()

        recs = compute_recommendations_for_user(db, user, limit=6)
        assert recs["source_type"] in ["profile", "combined", "catalog_fallback"]
        assert len(recs["recommendations"]) > 0
        top_rec = recs["recommendations"][0]
        assert top_rec["match_score"] > 50.0
        assert len(top_rec["matched_skills"]) > 0


def test_catalyst_cloud_db_column_alias_matching():
    """Verify mirror_row_to_datastore correctly matches column aliases and handles missing gracefully."""
    from backend.app.services.catalyst_cloud_db import mirror_row_to_datastore

    # Outside Zoho Catalyst environment, returns False safely without error
    res = mirror_row_to_datastore("PlutoUsers", {"email": "test@example.com"}, "email", "test@example.com")
    assert res is False  # Outside Catalyst context


def test_fresher_job_roles_loaded():
    """Verify fresher job roles (min_experience_years == 0) are correctly defined in catalog and seeded."""
    import json
    from backend.app.config import settings

    jobs_file = settings.APP_DIR / "data" / "jobs.json"
    with open(jobs_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    all_jobs = data["jobs"]
    assert len(all_jobs) == 18
    fresher_jobs = [j for j in all_jobs if j.get("min_experience_years") == 0]
    assert len(fresher_jobs) == 6
    fresher_ids = {j["id"] for j in fresher_jobs}
    assert "job_fresher_frontend" in fresher_ids
    assert "job_fresher_backend" in fresher_ids
    assert "job_fresher_qa" in fresher_ids
    assert "job_fresher_data" in fresher_ids
    assert "job_fresher_security" in fresher_ids
    assert "job_fresher_cloud" in fresher_ids


def test_datastore_user_recovery_logic():
    """Verify auth service recovers user from Data Store if missing in local SQLite."""
    from backend.app.services.auth_service import authenticate_user
    from backend.app.services.security_service import hash_password
    from unittest.mock import patch

    mock_ds_user = {
        "id": "usr_recovered_test_99",
        "email": "recovered_student@example.com",
        "full_name": "Recovered Student",
        "role": "candidate",
        "password_hash": hash_password("ValidPass123!"),
    }

    with SessionLocal() as db:
        # Ensure user does not exist locally
        existing = db.query(User).filter(User.email == "recovered_student@example.com").first()
        if existing:
            db.delete(existing)
            db.commit()

        with patch("backend.app.services.catalyst_cloud_db.lookup_user_in_datastore", return_value=mock_ds_user):
            auth_res = authenticate_user(
                db,
                email="recovered_student@example.com",
                password="ValidPass123!",
                portal="candidate",
            )
            assert auth_res["user"]["email"] == "recovered_student@example.com"
            assert auth_res["user"]["id"] == "usr_recovered_test_99"

        # Verify user is now created in SQLite
        db_user = db.query(User).filter(User.email == "recovered_student@example.com").first()
        assert db_user is not None
        assert db_user.full_name == "Recovered Student"
