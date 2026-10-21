"""Generate synthetic resume-job pairs, train screening classifiers, and generate test resume fixtures.

Implements Section 5.1 & 5.2 of docs/spec/5a-jobs-resume-questions.md.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import docx
import joblib
import numpy as np
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import GaussianNB

# Ensure root in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.app.config import settings

MODELS_DIR = settings.PROCESSED_DATA_DIR / "models"
FIXTURES_DIR = ROOT_DIR / "backend" / "tests" / "fixtures"
JOBS_FILE = ROOT_DIR / "backend" / "app" / "data" / "jobs.json"
TAXONOMY_FILE = ROOT_DIR / "backend" / "app" / "data" / "skills_taxonomy.json"
DATA_SPLIT_FILE = MODELS_DIR / "screening_dataset.joblib"


def generate_synthetic_data(jobs: list, n_samples: int = 1200):
    """Generate synthetic candidate feature vectors and binary screening labels."""
    random.seed(42)
    np.random.seed(42)

    X = []
    y = []

    for _ in range(n_samples):
        job = random.choice(jobs)
        req_skills = job.get("required_skills", [])
        pref_skills = job.get("preferred_skills", [])
        min_exp = job.get("min_experience_years", 3)
        threshold = job.get("pass_threshold", 0.65)

        # Candidate profile generation
        # Candidate skills coverage
        coverage_ratio = random.betavariate(2, 2)  # beta distribution between 0 and 1
        n_req_matched = int(round(coverage_ratio * len(req_skills)))
        n_req_missing = len(req_skills) - n_req_matched
        n_pref_matched = random.randint(0, len(pref_skills)) if pref_skills else 0

        req_score = n_req_matched / max(len(req_skills), 1)
        pref_score = n_pref_matched / max(len(pref_skills), 1) if pref_skills else 1.0
        skill_score = min(1.0, 0.8 * req_score + 0.2 * pref_score)

        # Experience
        cand_exp = max(0.0, random.gauss(min_exp + 0.5, 2.5))
        exp_score = min(1.0, (cand_exp / float(min_exp)) ** 1.2) if min_exp > 0 else 1.0

        # Education
        edu_score = random.choice([0.3, 0.6, 1.0, 1.0, 1.0])

        deterministic_fit = round(0.55 * skill_score + 0.25 * exp_score + 0.20 * edu_score, 3)

        # Ground truth label: pass if fit >= threshold AND missing_req == 0 (with 5% real-world noise)
        passed = 1 if (deterministic_fit >= threshold and n_req_missing == 0) else 0
        if random.random() < 0.04:  # 4% human reviewer variance
            passed = 1 - passed

        features = [
            skill_score,
            exp_score,
            edu_score,
            deterministic_fit,
            n_req_matched,
            n_req_missing,
        ]
        X.append(features)
        y.append(passed)

    X = np.array(X)
    y = np.array(y)
    return X, y


def generate_sample_resumes():
    """Create 5 realistic sample resumes (PDF and DOCX) in backend/tests/fixtures/."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Senior Security Analyst (PDF)
    pdf1_path = FIXTURES_DIR / "resume_senior_sec_analyst.pdf"
    c = canvas.Canvas(str(pdf1_path), pagesize=letter)
    text = c.beginText(50, 750)
    text.setFont("Helvetica-Bold", 14)
    text.textLine("Alex Vance - Senior Information Security Analyst")
    text.setFont("Helvetica", 10)
    text.textLine("Email: alex.vance@example.com | Phone: +1-555-0192 | LinkedIn: linkedin.com/in/alexvance")
    text.textLine("")
    text.setFont("Helvetica-Bold", 12)
    text.textLine("SUMMARY")
    text.setFont("Helvetica", 10)
    text.textLine("Cybersecurity specialist with over 5 years of experience in network security, threat mitigation, and zero trust.")
    text.textLine("")
    text.setFont("Helvetica-Bold", 12)
    text.textLine("SKILLS")
    text.setFont("Helvetica", 10)
    text.textLine("Network Security & Cryptography, Application Security, Zero Trust, IDS/IPS, Firewalls, TLS, Python, SIEM.")
    text.textLine("")
    text.setFont("Helvetica-Bold", 12)
    text.textLine("EXPERIENCE")
    text.setFont("Helvetica-Bold", 10)
    text.textLine("CyberNova Sentinel - Lead Security Analyst (Jan 2021 - Present)")
    text.setFont("Helvetica", 10)
    text.textLine("Led zero trust architecture adoption, automated incident response using Python, and audited TLS/SSL encryption.")
    text.textLine("")
    text.setFont("Helvetica-Bold", 10)
    text.textLine("DefenseNet Corp - Security Analyst (Jun 2018 - Dec 2020)")
    text.setFont("Helvetica", 10)
    text.textLine("Monitored intrusion detection systems, managed enterprise firewalls, and executed application vulnerability assessments.")
    text.textLine("")
    text.setFont("Helvetica-Bold", 12)
    text.textLine("EDUCATION")
    text.setFont("Helvetica", 10)
    text.textLine("Master of Science in Cybersecurity - National Institute of Technology (2018)")
    text.textLine("Bachelor of Technology in Computer Science (2016)")
    c.drawText(text)
    c.save()
    print(f"Generated: {pdf1_path.name}")

    # 2. Cloud & DevOps Lead (DOCX)
    docx1_path = FIXTURES_DIR / "resume_cloud_devops_lead.docx"
    doc = docx.Document()
    doc.add_heading("Marcus Brody - Lead Cloud & DevOps Engineer", level=0)
    doc.add_paragraph("marcus.brody@example.com | San Francisco, CA | github.com/marcusbrody")
    doc.add_heading("Summary", level=1)
    doc.add_paragraph("DevOps architect with 6 years of experience building resilient cloud systems on AWS and Kubernetes.")
    doc.add_heading("Skills", level=1)
    doc.add_paragraph("AWS, Docker, Kubernetes, CI/CD, Monitoring & Observability, Prometheus, Grafana, Istio, Python, Terraform.")
    doc.add_heading("Experience", level=1)
    doc.add_paragraph("Aetheria Cloud Systems - Staff DevOps Engineer (Mar 2020 - Present)")
    doc.add_paragraph("Architected multi-region Kubernetes clusters, implemented canary deployment pipelines, and deployed Prometheus telemetry.")
    doc.add_paragraph("CloudMatrix Inc - DevOps Engineer (Jan 2017 - Feb 2020)")
    doc.add_paragraph("Containerized legacy microservices using Docker and maintained Jenkins CI/CD automation.")
    doc.add_heading("Education", level=1)
    doc.add_paragraph("Bachelor of Science in Computer Science - University of California (2016)")
    doc.save(str(docx1_path))
    print(f"Generated: {docx1_path.name}")

    # 3. Machine Learning Engineer (PDF)
    pdf2_path = FIXTURES_DIR / "resume_ml_engineer.pdf"
    c2 = canvas.Canvas(str(pdf2_path), pagesize=letter)
    t2 = c2.beginText(50, 750)
    t2.setFont("Helvetica-Bold", 14)
    t2.textLine("Elena Rostova - Machine Learning Engineer")
    t2.setFont("Helvetica", 10)
    t2.textLine("elena.rostova@example.com | New York, NY")
    t2.textLine("")
    t2.setFont("Helvetica-Bold", 12)
    t2.textLine("SKILLS")
    t2.setFont("Helvetica", 10)
    t2.textLine("Python, Machine Learning, Deep Learning, Natural Language Processing, Computer Vision, PyTorch, SQL.")
    t2.textLine("")
    t2.setFont("Helvetica-Bold", 12)
    t2.textLine("EXPERIENCE")
    t2.setFont("Helvetica-Bold", 10)
    t2.textLine("Synapse Genomics AI - ML Engineer (Jan 2022 - Present)")
    t2.setFont("Helvetica", 10)
    t2.textLine("Developed deep neural networks for computer vision classification and fine-tuned NLP transformer architectures.")
    t2.textLine("")
    t2.setFont("Helvetica-Bold", 10)
    t2.textLine("DataCore Labs - Junior Data Scientist (Aug 2020 - Dec 2021)")
    t2.setFont("Helvetica", 10)
    t2.textLine("Engineered predictive classification pipelines using scikit-learn and monitored model data drift.")
    t2.textLine("")
    t2.setFont("Helvetica-Bold", 12)
    t2.textLine("EDUCATION")
    t2.setFont("Helvetica", 10)
    t2.textLine("Master of Science in Artificial Intelligence - Columbia University (2020)")
    t2.textLine("Bachelor of Science in Mathematics & Computer Science (2018)")
    c2.drawText(t2)
    c2.save()
    print(f"Generated: {pdf2_path.name}")

    # 4. Junior Frontend Developer (DOCX)
    docx2_path = FIXTURES_DIR / "resume_junior_frontend.docx"
    doc2 = docx.Document()
    doc2.add_heading("David Kim - Frontend Developer", level=0)
    doc2.add_paragraph("david.kim@example.com | Seattle, WA")
    doc2.add_heading("Skills", level=1)
    doc2.add_paragraph("React, JavaScript, TypeScript, CSS, HTML, Tailwind CSS, REST API.")
    doc2.add_heading("Experience", level=1)
    doc2.add_paragraph("OmniStack Platforms - Frontend Developer (Jun 2021 - Present)")
    doc2.add_paragraph("Built interactive web application modules using React and TypeScript, styling components with CSS and Tailwind.")
    doc2.add_heading("Education", level=1)
    doc2.add_paragraph("Bachelor of Science in Information Technology (2021)")
    doc2.save(str(docx2_path))
    print(f"Generated: {docx2_path.name}")

    # 5. Mismatched / Underqualified Candidate (PDF)
    pdf3_path = FIXTURES_DIR / "resume_mismatched_unqualified.pdf"
    c3 = canvas.Canvas(str(pdf3_path), pagesize=letter)
    t3 = c3.beginText(50, 750)
    t3.setFont("Helvetica-Bold", 14)
    t3.textLine("Sam Taylor - Marketing Associate")
    t3.setFont("Helvetica", 10)
    t3.textLine("sam.taylor@example.com | Chicago, IL")
    t3.textLine("")
    t3.setFont("Helvetica-Bold", 12)
    t3.textLine("SUMMARY")
    t3.setFont("Helvetica", 10)
    t3.textLine("Digital marketer with experience in social media campaigns, content strategy, and basic HTML formatting.")
    t3.textLine("")
    t3.setFont("Helvetica-Bold", 12)
    t3.textLine("SKILLS")
    t3.setFont("Helvetica", 10)
    t3.textLine("Content Writing, SEO, Social Media Management, Email Marketing, Basic HTML.")
    t3.textLine("")
    t3.setFont("Helvetica-Bold", 12)
    t3.textLine("EXPERIENCE")
    t3.setFont("Helvetica", 10)
    t3.textLine("GrowthMedia - Marketing Coordinator (Jan 2023 - Present)")
    t3.textLine("Managed editorial calendar and created newsletter content.")
    t3.textLine("")
    t3.setFont("Helvetica-Bold", 12)
    t3.textLine("EDUCATION")
    t3.setFont("Helvetica", 10)
    t3.textLine("Bachelor of Arts in Communications (2022)")
    c3.drawText(t3)
    c3.save()
    print(f"Generated: {pdf3_path.name}")


def main():
    print("=== PLUTO vProctor: Training Resume Screening ML Models ===")
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    with open(JOBS_FILE, "r", encoding="utf-8") as f:
        jobs = json.load(f).get("jobs", [])

    print(f"Loaded {len(jobs)} jobs for synthetic training set generation.")
    X, y = generate_synthetic_data(jobs, n_samples=1200)

    # Train / Val / Test split: 800 / 200 / 200
    X_train, y_train = X[:800], y[:800]
    X_val, y_val = X[800:1000], y[800:1000]
    X_test, y_test = X[1000:], y[1000:]

    # Save dataset split for evaluate_screening.py
    joblib.dump({
        "X_train": X_train, "y_train": y_train,
        "X_val": X_val, "y_val": y_val,
        "X_test": X_test, "y_test": y_test,
    }, DATA_SPLIT_FILE)

    # Train Logistic Regression
    lr = LogisticRegression(C=1.5, max_iter=300, random_state=42)
    lr.fit(X_train, y_train)
    val_acc_lr = lr.score(X_val, y_val)
    print(f"Logistic Regression Validation Accuracy: {val_acc_lr * 100:.2f}%")

    # Train Naive Bayes baseline
    nb = GaussianNB()
    nb.fit(X_train, y_train)
    val_acc_nb = nb.score(X_val, y_val)
    print(f"Naive Bayes Baseline Validation Accuracy: {val_acc_nb * 100:.2f}%")

    # Save best model (Logistic Regression)
    model_path = MODELS_DIR / "screening_model.joblib"
    joblib.dump(lr, model_path)
    print(f"Saved screening model to {model_path}")

    # Generate 5 sample resumes
    print("\nGenerating 5 realistic sample resumes (PDF and DOCX) in backend/tests/fixtures/...")
    generate_sample_resumes()

    print("\nTraining and fixture generation completed successfully.")


if __name__ == "__main__":
    main()
