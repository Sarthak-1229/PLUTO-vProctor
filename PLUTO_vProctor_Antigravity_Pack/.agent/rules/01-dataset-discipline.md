# Rule: dataset discipline (Always On)

- Real data: `datasets/data/` and `datasets/data1/`, each with train, val, test (`.json` or `.jsonl`). Treat the folder as read-only.
- Known format (from one inspected file): JSONL, fields `question` and `answer` only, short text, no metadata. Re-measure on the full data and print a schema report before coding the loader; the other files may differ.
- Dedupe across ALL files. If a question is in several splits keep it only in the highest-priority split: test > val > train (no leakage).
- train = fit; val = tune thresholds; test = final metrics only, touched once.
- Metadata (type, spoken_ok, skills, domain, cluster, difficulty, keywords) is DERIVED by `scripts/enrich_questions.py`; see `docs/spec/2B-dataset.md`.
- Synthetic data is allowed only for resume-job pairs and must be labelled synthetic everywhere.
