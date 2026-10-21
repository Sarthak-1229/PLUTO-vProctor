"""Seed SQLite database with jobs, companies, and enriched questions.

Implements Section 2B.2 and Phase 2 workflow step 5.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.app.db.database import Base, SessionLocal, engine
from backend.app.db.models import Company, Job, Question

JOBS_FILE = ROOT_DIR / "backend" / "app" / "data" / "jobs.json"
QUESTIONS_FILE = ROOT_DIR / "backend" / "app" / "data" / "processed" / "questions.json"


def seed_database():
    print("=== PLUTO vProctor: Seeding SQLite Database ===")

    # Create tables
    print("Creating database tables if not existing...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Load and seed companies and jobs
        if not JOBS_FILE.exists():
            print(f"Error: {JOBS_FILE} does not exist!")
            sys.exit(1)

        with open(JOBS_FILE, "r", encoding="utf-8") as f:
            jobs_data = json.load(f)

        companies_list = jobs_data.get("companies", [])
        jobs_list = jobs_data.get("jobs", [])

        # Clean existing jobs and companies
        db.query(Job).delete()
        db.query(Company).delete()
        db.commit()

        # Insert companies
        for c in companies_list:
            comp_obj = Company(
                id=c["id"],
                name=c["name"],
                industry=c["industry"],
                description=c.get("description", ""),
            )
            db.add(comp_obj)
        db.commit()
        print(f"Seeded {len(companies_list)} companies.")

        # Insert jobs
        for j in jobs_list:
            job_obj = Job(
                id=j["id"],
                title=j["title"],
                company=j["company"],
                company_id=j.get("company_id"),
                required_skills=j.get("required_skills", []),
                preferred_skills=j.get("preferred_skills", []),
                min_experience_years=j.get("min_experience_years", 0),
                education_levels=j.get("education_levels", []),
                skill_weights=j.get("skill_weights", {}),
                question_domains=j.get("question_domains", []),
                pass_threshold=j.get("pass_threshold", 0.65),
            )
            db.add(job_obj)
        db.commit()
        print(f"Seeded {len(jobs_list)} jobs.")

        # Seed questions
        if not QUESTIONS_FILE.exists():
            print(f"Error: {QUESTIONS_FILE} does not exist! Run enrich_questions.py first.")
            sys.exit(1)

        with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
            questions_list = json.load(f)

        db.query(Question).delete()
        db.commit()

        q_objs = []
        for q in questions_list:
            q_obj = Question(
                id=q["id"],
                question=q["question"],
                answer=q["answer"],
                split=q.get("split", "train"),
                source_folder=q.get("source_folder", ""),
                type=q.get("type", "explain"),
                spoken_ok=q.get("spoken_ok", True),
                skills=q.get("skills", []),
                domain=q.get("domain", "General"),
                cluster_id=q.get("cluster_id", 0),
                difficulty=q.get("difficulty", 1),
                expected_keywords=q.get("expected_keywords", []),
                ideal_answer_summary=q.get("ideal_answer_summary", q["answer"]),
                est_seconds=q.get("est_seconds", 70),
            )
            q_objs.append(q_obj)

        db.bulk_save_objects(q_objs)
        db.commit()
        print(f"Seeded {len(q_objs)} questions into SQLite database.")

        # Verify
        c_count = db.query(Company).count()
        j_count = db.query(Job).count()
        q_count = db.query(Question).count()
        spoken_q_count = db.query(Question).filter(Question.spoken_ok.is_(True)).count()

        print("\nDatabase Verification Summary:")
        print(f"  - Companies : {c_count}")
        print(f"  - Jobs      : {j_count}")
        print(f"  - Questions : {q_count} total ({spoken_q_count} spoken_ok)")

        print("\nSQLite database successfully seeded at backend/app/pluto.db!")

    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
