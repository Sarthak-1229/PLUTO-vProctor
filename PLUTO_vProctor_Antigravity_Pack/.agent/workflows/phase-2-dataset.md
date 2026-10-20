---
description: PLUTO Phase 2: ingest, clean, dedupe and enrich my real datasets
---

# Phase 2: Dataset ingestion and enrichment

Read: `docs/spec/2B-dataset.md`, then `docs/spec/5a-jobs-resume-questions.md` (section 5.1 only).

1. FIRST print a schema report for every file in `datasets/data*/` (format, rows, keys, empty fields, length stats). Adapt the loader to what is really there.
2. `scripts/ingest_datasets.py`: defensive loading, cleaning, cross-folder dedup (exact + MinHash + embedding), leakage prevention (test > val > train), stable ids, output `qa_clean.jsonl` and `docs/DATASET_REPORT.md`.
3. `scripts/enrich_questions.py`: type, spoken_ok, skills, domain (rules + NB/LogReg), K-Means cluster (silhouette on val), difficulty, expected_keywords, est_seconds, embeddings.
4. Build `skills_taxonomy.json` (from the data + curated), `fillers.json`, and the hand-written `jobs.json` (12+ jobs, 5-6 fictional companies).
5. `scripts/seed_db.py` loads everything into SQLite.
6. Print the coverage table (questions per domain/type/difficulty/split). Every job must have at least 25 usable questions; fix the job-to-domain mapping if not.

**STOP after this phase and show me DATASET_REPORT.md and the coverage table for review.**
