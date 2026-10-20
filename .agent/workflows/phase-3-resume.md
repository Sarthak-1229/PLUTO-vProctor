---
description: PLUTO Phase 3: resume parsing, scoring and screening classifier
---

# Phase 3: Resume pipeline

Read: `docs/spec/5a-jobs-resume-questions.md` (section 5.2).

1. PDF/DOCX text extraction, section segmentation, layered skill extraction (Trie, fuzzy Levenshtein, MiniLM semantic), experience parsing with interval merging, education detection.
2. Deterministic fit score and per-category breakdown; screening status with reasons. Rejected candidates can still proceed to the interview.
3. `scripts/train_models.py`: generate labelled SYNTHETIC resume-job pairs, train Logistic Regression (and Naive Bayes baseline), save with joblib; write 5 sample resumes (PDF and DOCX) into `backend/tests/fixtures/`.
4. `scripts/evaluate_screening.py`: accuracy, precision, recall, F1, confusion matrix.
5. Endpoints: `GET /api/jobs`, `GET /api/jobs/search`, `POST /api/resume/upload`.

Acceptance: sample resumes parse correctly, screening endpoint works, metrics printed.
