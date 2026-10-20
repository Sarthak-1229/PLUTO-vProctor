---
description: PLUTO: run every evaluation script and summarise metrics
---

# Run all evaluations

1. Run `backend/scripts/evaluate_domain.py`, `evaluate_retrieval.py`, `evaluate_answer_relevance.py`, `evaluate_screening.py`, `evaluate_selection.py`, and `benchmark_algorithms.py`.
2. Collect the metrics into one markdown table in `docs/EVALUATION_SUMMARY.md` (test split only for final numbers; val for tuning).
3. Flag anything that looks like leakage (test metrics suspiciously near 1.0) and investigate.
