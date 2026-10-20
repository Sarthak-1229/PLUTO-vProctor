---
description: PLUTO Phase 4: question filtering and selection engine
---

# Phase 4: Question engine

Read: `docs/spec/5a-jobs-resume-questions.md` (section 5.3) and `docs/spec/2B-dataset.md` (2B.4 item 5).

1. Inverted index, relevance scoring, manual min-heap top-K, MMR, 0/1 knapsack time budget, merge-sort ordering, cluster/domain caps, no repeats per session.
2. RAG follow-ups: retrieve 2 nearest dataset Q&A pairs, ask the LLM for one short JSON follow-up (max 3 per interview), with fallback to none.
3. `scripts/evaluate_selection.py`: compare random vs relevance vs relevance+MMR vs relevance+MMR+knapsack on topic coverage, redundancy and total time; tune weights on val.
4. Endpoint `POST /api/interview/{sid}/start`.

Acceptance: sample resumes produce sensible, diverse, time-bounded question lists; comparison table printed.
