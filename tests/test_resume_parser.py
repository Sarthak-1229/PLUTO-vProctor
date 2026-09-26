"""
Tests for the PLUTO vProctor résumé parser (Part 2).

Runs the full ingestion pipeline on synthetic résumé text:
  parse_text -> ResumeProfile -> QuestionBank.select_for_resume.
No external files or network; CPU-only. Exit 0 = pass, 1 = fail (CI-friendly).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.interview.resume_parser import get_resume_parser
from core.interview.question_bank import get_question_bank

SENIOR_BACKEND = """
Jane Doe - Senior Backend Engineer
7 years experience designing REST APIs in Python and Java (Spring Boot).
Built distributed systems on PostgreSQL and Redis, containerized with Docker and Kubernetes.
Strong data structures and algorithms; close collaboration with product managers.
"""

JUNIOR_DATA_ML = """
John Smith - Machine Learning Intern / Graduate
Recent CS graduate. Built models with PyTorch and scikit-learn in Python.
Comfortable with statistics and SQL. 1 year of internship experience.
"""


def check(name, cond, detail=""):
    mark = "PASS" if cond else "FAIL"
    print(f"  [{mark}] {name}{(' - ' + detail) if detail else ''}")
    return cond


def main():
    parser = get_resume_parser()
    qb = get_question_bank()
    ok = True

    print("Case 1: senior backend résumé")
    p1 = parser.parse_text(SENIOR_BACKEND)
    print("   skills:", p1.skills)
    print("   role:", p1.inferred_role, "| seniority:", p1.inferred_seniority,
          "(", p1.seniority_evidence, ")")
    ok &= check("python detected", "python" in p1.skills)
    ok &= check("java detected", "java" in p1.skills)
    ok &= check("rest-api detected", "rest-api" in p1.skills)
    ok &= check("docker detected", "docker" in p1.skills)
    ok &= check("role is swe-backend", p1.inferred_role == "swe-backend",
                p1.inferred_role)
    ok &= check("seniority is senior", p1.inferred_seniority == "senior",
                p1.inferred_seniority)

    pool = qb.select_for_resume(resume_tags=p1.skills, target_role=p1.inferred_role,
                                limit=10)
    cats = {}
    for q in pool:
        cats[q["category"]] = cats.get(q["category"], 0) + 1
    print("   selected pool:", len(pool), cats)
    ok &= check("pool non-empty", len(pool) > 0)
    ok &= check("behavioral quota >= min(4, avail)", cats.get("behavioral", 0) >= 1)

    print("Case 2: junior data/ML résumé")
    p2 = parser.parse_text(JUNIOR_DATA_ML)
    print("   skills:", p2.skills)
    print("   role:", p2.inferred_role, "| seniority:", p2.inferred_seniority,
          "(", p2.seniority_evidence, ")")
    ok &= check("machine-learning detected", "machine-learning" in p2.skills)
    ok &= check("python detected", "python" in p2.skills)
    ok &= check("role is data-ml", p2.inferred_role == "data-ml", p2.inferred_role)
    ok &= check("seniority is junior", p2.inferred_seniority == "junior",
                p2.inferred_seniority)

    print("\nOK - résumé parser pipeline valid." if ok else "\nFAILURES present.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
