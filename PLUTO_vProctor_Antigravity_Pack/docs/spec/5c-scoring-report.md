<!-- Spec file for PLUTO vProctor. Section numbers (2B, 5.3, ...) refer to the files in docs/spec/. -->

## 5. Feature specifications (part C: scoring, answers, report)

### 5.6 Scoring engine
Start from 100 per category, apply deductions, clamp at 0, then combine. All constants live in `config.py`.

| Category | Weight | Deduction examples |
|---|---|---|
| Resume fit | 20% | score = fit × 100 |
| Eye contact | 20% | −1 per started look-away, −0.5 per extra second beyond 2 s (cap per event) |
| Body language and motion | 15% | −1 excessive motion, −1.5 posture, −3 face missing > 3 s |
| Confidence (fluency) | 25% | −0.5 per filler (cap per answer), −1 per long pause, −1.5 per late start, pace penalties |
| Answer quality | 20% | keyword coverage + embedding similarity to ideal answer + LLM rubric (0–10, JSON) |

- Every deduction is a row: `{id, t (seconds), mmss, category, type, points, reason, question_id}`.
- Sort deduction rows chronologically using the custom merge sort; support **binary search** over the sorted list to find "which deductions occur around time T" when the user scrubs the video.
- Final grade bands (A/B/C/D) and a readiness label.

### 5.7 Answer quality (dataset-backed, LLM used sparingly)
Every question has a **reference answer from the dataset** (short: about 11 to 27 words). A spoken answer will be much longer, so do **not** use length-penalising metrics or Jaccard on whole answers. Use asymmetric, recall-oriented measures.
- **Step 1 (algorithmic, trained on the dataset):**
  - keyword recall: fraction of `expected_keywords` (lemmatised) present in the transcript, with fuzzy matching via Levenshtein;
  - MiniLM cosine between the transcript and the reference answer, and between the transcript and the question;
  - BM25 and TF-IDF cosine;
  - feed these into the **answer-relevance Logistic Regression** trained in 2B.4 item 3; its probability is the algorithmic score. Calibrate the thresholds on the val split.
- **Step 2 (LLM):** prompt Qwen2.5-3B with the question, the reference answer and the clipped transcript (about 250 words) and ask for strict JSON `{"relevance":0-10,"clarity":0-10,"depth":0-10,"one_line_feedback":"..."}`. Include 2 retrieved neighbour Q&A pairs as style examples. Validate with Pydantic; retry once.
- **Blend:** 60% algorithmic, 40% LLM. If the LLM fails twice, use the algorithmic score alone.
- The feedback shown to the candidate always includes the **reference answer** from the dataset ("A strong answer mentions: ...") and the keywords the candidate missed.

### 5.8 Report
- Overall score, per-category scores (radar chart), screening result with reasons.
- **LLM-generated summary** (strengths, weaknesses, 5 concrete tips) from the structured stats only (never the raw video); fallback to template-based text if the LLM fails.
- **Deduction timeline:** a table plus a marker strip over the video timeline; clicking a row seeks the `<video>` to that mm:ss. Show filler words highlighted inside the transcript.
- Per-question breakdown with transcript, answer quality feedback and deductions.
- Export report as PDF (use `reportlab` or `weasyprint`) and as JSON.
