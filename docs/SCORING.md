# PLUTO vProctor: Scoring Engine, Grading Formulas & Traceability Specification

## 1. Overview and Core Philosophy

In PLUTO vProctor, interview scores are **deterministic, explainable, and monotonic**:
1. Every proctoring penalty and fluency hesitation is an explicit deduction row in the timeline with a `mm:ss` timestamp.
2. The final scores are **exactly reconstructable** by subtracting deductions from category baselines.
3. Spoken answers are graded with strict monotonicity:
   $$\text{Score}(\text{Reference}) > \text{Score}(\text{Partial}) > \text{Score}(\text{Vague}) > \text{Score}(\text{Off-Topic}) \ge \text{Score}(\text{Empty})$$

---

## 2. Four Score Buckets & Weights

$$\text{Overall Score} = 0.35 \times S_{\text{tech}} + 0.25 \times S_{\text{fluency}} + 0.25 \times S_{\text{proctor}} + 0.15 \times S_{\text{resume}}$$

| Bucket | Weight | Starting Base | Sources & Penalties |
|---|---|---|---|
| **Technical Depth** | **35%** | $0.0$ to $100.0$ | Average score across technical interview questions evaluated against gold dataset answers. |
| **Fluency & Confidence** | **25%** | $100.0$ | Deductions from hard fillers ($1.5$/100 words), soft fillers ($0.5$/100 words), phrase fillers ($0.5$), hesitations ($0.3$), long pauses ($1.0$), and rushed/slow pace deviation. Cap: $8.0$ pts/answer. |
| **Proctoring Integrity** | **25%** | $100.0$ | Deductions from directional look-aways (`LOOK_DOWN`: $1.5$/s, `LOOK_SIDE`: $1.0$/s, `LOOK_UP`: $0.5$/s), face missing ($2.0$/s), multiple faces ($2.5$/s), excessive motion ($1.0$), posture slump ($0.5$), tab switch ($2.0$), and window blur ($1.0$). |
| **Resume Fit** | **15%** | $0.0$ to $100.0$ | Pre-screening fit score ($\text{screening\_fit} \times 100$) based on skills, education, and domain requirements. |

---

## 3. Technical Answer Grading Architecture

Each candidate response is aligned with its question interval $[t_{\text{start}}, t_{\text{end}}]$ from the recording clock and evaluated via a 60/40 hybrid blend:

$$\text{Answer Score} = 0.60 \times \text{Score}_{\text{algorithmic}} + 0.40 \times \text{Score}_{\text{LLM}}$$

### 3.1 Algorithmic Evaluation (60%)
- **Semantic Embedding Similarity ($E$)**: Cosine similarity via `all-MiniLM-L6-v2` against dataset ground truth.
- **Fuzzy Keyword Recall ($K$)**: Recall of technical expected keywords using Levenshtein distance $\le 1$ to tolerate minor ASR phonetic variances.
- **TF-IDF & BM25 Relevance ($T, B$)**: Lexical match against technical corpus.
- **Off-Topic Gate**: If $E < 0.25$, answer is flagged as off-topic and capped at $\le 15.0$.
- **Short Answer Cap**: Answers under 7 words are capped at $\le 45.0$. Empty answers score $0.0$.

### 3.2 LLM Rubric Evaluation (40%)
- Structured JSON prompt evaluated via local `Qwen2.5:3b` (or cloud provider if configured):
  $$\text{Score}_{\text{LLM}} = \frac{\text{Relevance} + \text{Clarity} + \text{Depth}}{3.0} \times 10.0$$
- If the LLM is offline or times out, the system automatically falls back to $100\%$ algorithmic score without failing the interview report.

---

## 4. Deduction Row Traceability Schema

Every deduction event recorded in SQLite and rendered in the report adheres to the strict schema:

```json
{
  "id": "evt_lookaway_0883d7c1",
  "t": 7.3,
  "mmss": "00:07",
  "bucket": "Proctoring Integrity",
  "category": "Eye contact",
  "type": "LOOK_DOWN",
  "points": 6.4,
  "reason": "Candidate looked downward (reading notes/screen) for 4.3s",
  "question_id": "q_102",
  "evidence_ref": "LOOK_DOWN"
}
```

### Exact Score Reconstruction Formula:
$$S_{\text{proctor}} = \max\left(0.0, 100.0 - \sum_{e \in \text{Proctoring}} e.\text{points}\right)$$
$$S_{\text{fluency}} = \max\left(0.0, 100.0 - \sum_{e \in \text{Fluency}} e.\text{points}\right)$$

---

## 5. Timeline Scrubbing via Binary Search

Clicking any deduction row in the UI seeks the video player to the exact event:
- Chronologically ordered using merge sort ($O(N \log N)$).
- Scrubbing and nearby deduction retrieval uses binary search (`lower_bound` / `upper_bound` in $O(\log N)$).
- Seek accuracy tolerance: $\le 0.3\text{ seconds}$.

---

## 6. Readiness Bands

- **Grade A ($\ge 85.0$)**: Interview Ready (Strong Recommendation)
- **Grade B ($70.0 - 84.9$)**: Ready with Minor Polish
- **Grade C ($55.0 - 69.9$)**: Needs Practice Before Real Interview
- **Grade D ($< 55.0$)**: Requires Substantial Preparation
