"""API endpoints for job listings and Trie-based search."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.algorithms.trie import Trie
from backend.app.db.database import get_db
from backend.app.db.models import Company, Job

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])

# In-memory Trie index for fast prefix autocomplete
job_trie = Trie()
_job_index: Dict[str, List[Dict[str, Any]]] = {}  # prefix -> jobs list


def _build_trie_index(db: Session):
    global job_trie, _job_index
    if _job_index:
        return
    jobs = db.query(Job).all()
    for j in jobs:
        j_dict = {
            "id": j.id,
            "title": j.title,
            "company": j.company,
            "company_id": j.company_id,
            "required_skills": j.required_skills or [],
            "preferred_skills": j.preferred_skills or [],
            "min_experience_years": j.min_experience_years,
            "education_levels": j.education_levels or [],
            "question_domains": j.question_domains or [],
            "pass_threshold": j.pass_threshold,
        }
        # Index title tokens
        for token in j.title.lower().split():
            clean = "".join(c for c in token if c.isalnum())
            if len(clean) >= 2:
                job_trie.insert(clean)
                _job_index.setdefault(clean, []).append(j_dict)
        # Index company tokens
        for token in (j.company or "").lower().split():
            clean = "".join(c for c in token if c.isalnum())
            if len(clean) >= 2:
                job_trie.insert(clean)
                _job_index.setdefault(clean, []).append(j_dict)
        # Index skills
        for skill in (j.required_skills or []):
            for token in skill.lower().split():
                clean = "".join(c for c in token if c.isalnum())
                if len(clean) >= 2:
                    job_trie.insert(clean)
                    _job_index.setdefault(clean, []).append(j_dict)


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def list_jobs(db: Session = Depends(get_db)):
    """Retrieve all available job profiles."""
    jobs = db.query(Job).all()
    if not jobs:
        import json
        from backend.app.config import settings
        jobs_file = settings.BASE_DIR / "backend" / "app" / "data" / "jobs.json"
        if jobs_file.exists():
            with open(jobs_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("jobs", [])
    return [
        {
            "id": j.id,
            "title": j.title,
            "company": j.company,
            "company_id": j.company_id,
            "required_skills": j.required_skills or [],
            "preferred_skills": j.preferred_skills or [],
            "min_experience_years": j.min_experience_years,
            "education_levels": j.education_levels or [],
            "question_domains": j.question_domains or [],
            "pass_threshold": j.pass_threshold,
        }
        for j in jobs
    ]


@router.get("/search", response_model=List[Dict[str, Any]])
def search_jobs(q: str = Query("", min_length=1), db: Session = Depends(get_db)):
    """Search job listings using the hand-implemented Trie index."""
    _build_trie_index(db)
    query_clean = "".join(c for c in q.lower().strip() if c.isalnum())
    if not query_clean:
        return list_jobs(db)

    # Use Trie autocomplete to find matching keywords
    matching_words = job_trie.autocomplete(query_clean)[:10]
    seen_job_ids = set()
    results = []

    for word in matching_words:
        for job in _job_index.get(word, []):
            if job["id"] not in seen_job_ids:
                seen_job_ids.add(job["id"])
                results.append(job)

    # Fallback substring search if Trie had no matches
    if not results:
        all_jobs = db.query(Job).all()
        q_low = q.lower()
        for j in all_jobs:
            if (
                q_low in j.title.lower()
                or q_low in j.company.lower()
                or any(q_low in s.lower() for s in (j.required_skills or []))
                or any(q_low in d.lower() for d in (j.question_domains or []))
            ):
                if j.id not in seen_job_ids:
                    seen_job_ids.add(j.id)
                    results.append({
                        "id": j.id,
                        "title": j.title,
                        "company": j.company,
                        "company_id": j.company_id,
                        "required_skills": j.required_skills or [],
                        "preferred_skills": j.preferred_skills or [],
                        "min_experience_years": j.min_experience_years,
                        "education_levels": j.education_levels or [],
                        "question_domains": j.question_domains or [],
                        "pass_threshold": j.pass_threshold,
                    })

    return results


@router.get("/{job_id}", response_model=Dict[str, Any])
def get_job(job_id: str, db: Session = Depends(get_db)):
    """Retrieve details of a specific job profile."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "company_id": job.company_id,
        "required_skills": job.required_skills or [],
        "preferred_skills": job.preferred_skills or [],
        "min_experience_years": job.min_experience_years,
        "education_levels": job.education_levels or [],
        "question_domains": job.question_domains or [],
        "pass_threshold": job.pass_threshold,
    }
