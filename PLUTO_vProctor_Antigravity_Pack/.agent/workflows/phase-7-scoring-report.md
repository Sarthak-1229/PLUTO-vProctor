---
description: PLUTO Phase 7: answer evaluation, scoring engine and report
---

# Phase 7: Answer evaluation, scoring, report

Read: `docs/spec/5c-scoring-report.md` and `docs/spec/2B-dataset.md` (2B.4 items 2 and 3).

1. `scripts/evaluate_retrieval.py` (TF-IDF vs BM25 vs MiniLM: Recall@1/3/5, MRR) and `scripts/evaluate_answer_relevance.py` (hard negatives; Logistic Regression vs Gradient Boosting; accuracy, precision, recall, F1, ROC-AUC on test).
2. `answer_eval_service.py`: algorithmic score + LLM rubric (60/40), fallback to algorithmic only.
3. `scoring_engine.py`: per-category scoring and a deduction log (merge-sorted, binary-searchable by timestamp).
4. LLM summary (structured stats only) with template fallback; PDF/JSON export.
5. Report page: radar chart, screening reasons, clickable deduction timeline that seeks the video to mm:ss, transcript with highlighted fillers, reference answers and missed keywords per question.

Acceptance: a completed session yields a full report and every deduction row seeks the video correctly.
