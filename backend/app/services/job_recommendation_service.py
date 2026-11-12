"""Universal candidate job & role-template recommendations requiring zero prior interviews."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Set

from sqlalchemy.orm import Session

from backend.app.db.models import (
    CandidateProfile,
    InterviewSession,
    Job,
    JobRecommendation,
    JobRoleTemplate,
    Resume,
    ResumeProfile,
    User,
)
from backend.app.services.security_service import utcnow_naive

_DEFAULT_ROLE_TEMPLATES: List[Dict[str, Any]] = [
    {
        "slug": "backend-developer-entry",
        "title": "Junior Backend Developer",
        "level": "entry",
        "domain": "Web Development",
        "required_skills_json": ["Python", "SQL", "REST APIs", "Git"],
        "preferred_skills_json": ["Docker", "PostgreSQL", "FastAPI"],
        "min_experience_years": 0.0,
        "education_levels_json": ["Bachelor", "Diploma", "Master"],
        "description": "Entry-level backend API and relational database role suited for recent graduates and freshers.",
        "mapped_job_id": "job_backend_eng",
    },
    {
        "slug": "frontend-react-entry",
        "title": "Frontend React Developer (Entry)",
        "level": "entry",
        "domain": "Web Development",
        "required_skills_json": ["JavaScript", "React", "HTML", "CSS"],
        "preferred_skills_json": ["TypeScript", "Tailwind CSS", "Git"],
        "min_experience_years": 0.0,
        "education_levels_json": ["Bachelor", "Diploma", "Master"],
        "description": "Build accessible, responsive web interfaces using modern React components and state management.",
        "mapped_job_id": "job_frontend_eng",
    },
    {
        "slug": "cloud-devops-intern",
        "title": "Cloud & DevOps Intern / Associate",
        "level": "intern",
        "domain": "Cloud & DevOps",
        "required_skills_json": ["Linux", "Docker", "Git", "AWS"],
        "preferred_skills_json": ["Kubernetes", "CI/CD", "Python"],
        "min_experience_years": 0.0,
        "education_levels_json": ["Bachelor", "Master"],
        "description": "Assist engineering teams with containerization, CI/CD automation, and cloud deployments.",
        "mapped_job_id": "job_cloud_eng",
    },
    {
        "slug": "cybersecurity-analyst-entry",
        "title": "Junior Cybersecurity Analyst",
        "level": "entry",
        "domain": "Security",
        "required_skills_json": ["Network Security & Cryptography", "Application Security", "Operating Systems & Networking"],
        "preferred_skills_json": ["Python", "Cloud Architecture", "Linux"],
        "min_experience_years": 0.0,
        "education_levels_json": ["Bachelor", "Master"],
        "description": "Monitor application threats, harden endpoints, and perform foundational security triage.",
        "mapped_job_id": "job_sec_analyst",
    },
    {
        "slug": "data-analyst-ml-fresher",
        "title": "Junior Data Analyst / ML Associate",
        "level": "entry",
        "domain": "Data Science/ML",
        "required_skills_json": ["Python", "SQL", "Data Analysis & Pandas"],
        "preferred_skills_json": ["Machine Learning", "Statistics", "PyTorch"],
        "min_experience_years": 0.0,
        "education_levels_json": ["Bachelor", "Master"],
        "description": "Analyze structured datasets, build reporting metrics, and prototype ML baselines.",
        "mapped_job_id": "job_ml_eng",
    },
    {
        "slug": "full-stack-engineer-entry",
        "title": "Full Stack Software Engineer (Fresher)",
        "level": "entry",
        "domain": "Software Engineering",
        "required_skills_json": ["JavaScript", "Python", "SQL", "React"],
        "preferred_skills_json": ["Docker", "TypeScript", "REST APIs"],
        "min_experience_years": 0.0,
        "education_levels_json": ["Bachelor", "Master"],
        "description": "Deliver end-to-end features across React frontend services and backend APIs.",
        "mapped_job_id": "job_fullstack_eng",
    },
]


def ensure_role_templates_seeded(db: Session) -> None:
    """Idempotently ensure starter fresher/entry role templates exist in database."""
    existing_slugs = {row[0] for row in db.query(JobRoleTemplate.slug).all()}
    existing_job_ids = {row[0] for row in db.query(Job.id).all()}
    now = utcnow_naive()
    added = False
    for tmpl in _DEFAULT_ROLE_TEMPLATES:
        if tmpl["slug"] in existing_slugs:
            continue
        mapped_id = tmpl["mapped_job_id"] if tmpl["mapped_job_id"] in existing_job_ids else None
        db.add(
            JobRoleTemplate(
                id=f"tmpl_{uuid.uuid4().hex[:12]}",
                slug=tmpl["slug"],
                title=tmpl["title"],
                level=tmpl["level"],
                domain=tmpl["domain"],
                required_skills_json=tmpl["required_skills_json"],
                preferred_skills_json=tmpl["preferred_skills_json"],
                min_experience_years=tmpl["min_experience_years"],
                education_levels_json=tmpl["education_levels_json"],
                description=tmpl["description"],
                mapped_job_id=mapped_id,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        added = True
    if added:
        db.commit()


def _skill_matches(candidate_skills_norm: Set[str], target_skill: str) -> bool:
    t = target_skill.strip().lower()
    if not t:
        return False
    if t in candidate_skills_norm:
        return True
    t_tokens = {tok for tok in t.replace("&", " ").replace("/", " ").split() if len(tok) >= 3}
    for cs in candidate_skills_norm:
        if cs in t or t in cs:
            return True
        cs_tokens = {tok for tok in cs.replace("&", " ").replace("/", " ").split() if len(tok) >= 3}
        if t_tokens and cs_tokens and (len(t_tokens & cs_tokens) >= max(1, len(t_tokens) // 2)):
            return True
    return False


def _score_target(
    *,
    title: str,
    required_skills: List[str],
    preferred_skills: List[str],
    min_exp: float,
    candidate_skills: Set[str],
    candidate_exp: float,
    preferred_roles: Set[str],
) -> tuple[float, List[str], List[str], str]:
    matched_req = [s for s in required_skills if _skill_matches(candidate_skills, s)]
    missing_req = [s for s in required_skills if s not in matched_req]
    matched_pref = [s for s in preferred_skills if _skill_matches(candidate_skills, s)]

    req_ratio = (len(matched_req) / len(required_skills)) if required_skills else 0.5
    pref_ratio = (len(matched_pref) / len(preferred_skills)) if preferred_skills else 0.5
    exp_score = 1.0 if candidate_exp >= float(min_exp or 0.0) else max(0.25, candidate_exp / max(1.0, float(min_exp or 1.0)))
    title_low = title.lower()
    role_affinity = 1.0 if any(pref in title_low or title_low in pref for pref in preferred_roles) else 0.3

    raw_score = (0.65 * req_ratio + 0.15 * pref_ratio + 0.10 * exp_score + 0.10 * role_affinity) * 100.0
    score = round(min(99.0, max(5.0, raw_score)), 1)

    matched_all = list(dict.fromkeys(matched_req + matched_pref))
    if matched_all:
        reason = f"Matches {', '.join(matched_all[:4])}"
        if missing_req:
            reason += f"; build next: {', '.join(missing_req[:2])}"
    elif candidate_skills:
        reason = f"Transferable baseline; focus on {', '.join(required_skills[:3])}"
    else:
        reason = f"Entry-ready template; add skills like {', '.join(required_skills[:3])} to improve accuracy"

    return score, matched_all, missing_req, reason


def compute_recommendations_for_user(db: Session, user: User, limit: int = 12) -> Dict[str, Any]:
    """Compute universal ranked job + role-template recommendations for any authenticated candidate."""
    ensure_role_templates_seeded(db)

    profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == user.id).first()
    latest_resume_pair = (
        db.query(Resume, ResumeProfile)
        .join(ResumeProfile, ResumeProfile.resume_id == Resume.id)
        .filter(Resume.user_id == user.id, Resume.is_active.is_(True))
        .order_by(Resume.created_at.desc())
        .first()
    )

    profile_skills = list(profile.technical_skills_json or []) if profile else []
    profile_exp = float(profile.experience_years or 0.0) if profile else 0.0
    preferred_roles = {str(r).strip().lower() for r in (profile.preferred_roles_json or []) if str(r).strip()} if profile else set()

    resume_skills: List[str] = []
    resume_exp = 0.0
    if latest_resume_pair is not None:
        _, rp = latest_resume_pair
        effective = {**(rp.extracted_data_json or {}), **(rp.edited_data_json or {})}
        resume_skills = list(effective.get("skills") or [])
        resume_exp = float(effective.get("experience_years") or 0.0)

    has_profile_signals = bool(profile_skills or (profile and (profile.headline or profile.preferred_roles_json)))
    has_resume_signals = latest_resume_pair is not None
    if has_profile_signals and has_resume_signals:
        source_type = "combined"
    elif has_resume_signals:
        source_type = "resume"
    elif has_profile_signals:
        source_type = "profile"
    else:
        source_type = "catalog_fallback"

    combined_skills = {str(s).strip().lower() for s in (profile_skills + resume_skills) if str(s).strip()}
    effective_exp = max(profile_exp, resume_exp)

    completed_count = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.candidate_user_id == user.id,
            InterviewSession.interview_status.in_(["EVALUATED", "COMPLETED", "RECORDED"]),
        )
        .count()
    )

    candidates: List[Dict[str, Any]] = []
    for j in db.query(Job).all():
        score, matched, missing, reason = _score_target(
            title=j.title,
            required_skills=list(j.required_skills or []),
            preferred_skills=list(j.preferred_skills or []),
            min_exp=float(j.min_experience_years or 0.0),
            candidate_skills=combined_skills,
            candidate_exp=effective_exp,
            preferred_roles=preferred_roles,
        )
        candidates.append(
            {
                "target_type": "job",
                "target_id": j.id,
                "interview_job_id": j.id,
                "title": j.title,
                "company": j.company,
                "level": "mid" if (j.min_experience_years or 0) >= 2 else "entry",
                "domain": ", ".join(j.question_domains or []) or "Engineering",
                "match_score": score,
                "matched_skills": matched,
                "missing_skills": missing,
                "why_recommended": reason,
            }
        )

    for t in db.query(JobRoleTemplate).filter(JobRoleTemplate.is_active.is_(True)).all():
        score, matched, missing, reason = _score_target(
            title=t.title,
            required_skills=list(t.required_skills_json or []),
            preferred_skills=list(t.preferred_skills_json or []),
            min_exp=float(t.min_experience_years or 0.0),
            candidate_skills=combined_skills,
            candidate_exp=effective_exp,
            preferred_roles=preferred_roles,
        )
        candidates.append(
            {
                "target_type": "role_template",
                "target_id": t.id,
                "interview_job_id": t.mapped_job_id,
                "title": t.title,
                "company": "Role Template",
                "level": t.level,
                "domain": t.domain,
                "match_score": score,
                "matched_skills": matched,
                "missing_skills": missing,
                "why_recommended": reason,
            }
        )

    candidates.sort(key=lambda item: (-item["match_score"], 0 if item["target_type"] == "job" else 1, item["title"]))
    top = candidates[:limit]

    # Persist latest recommendations snapshot cleanly for this candidate
    db.query(JobRecommendation).filter(JobRecommendation.user_id == user.id).delete()
    now = utcnow_naive()
    for item in top:
        db.add(
            JobRecommendation(
                id=f"jrec_{uuid.uuid4().hex[:16]}",
                user_id=user.id,
                source_type=source_type,
                target_type=item["target_type"],
                target_id=item["target_id"],
                title=item["title"],
                match_score=item["match_score"],
                matched_skills_json=item["matched_skills"],
                missing_skills_json=item["missing_skills"],
                explanation=item["why_recommended"],
                created_at=now,
            )
        )
    db.commit()

    return {
        "source_type": source_type,
        "has_completed_interview": completed_count > 0,
        "candidate_skills": sorted({s for s in (profile_skills + resume_skills) if str(s).strip()}),
        "experience_years": effective_exp,
        "recommendations": top,
    }

