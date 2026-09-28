# PLUTO vProctor — Classical-AIML Layer

**MDM AIML project, requirement 6.** The interview app already satisfied its four
functional requirements (intake, résumé-grounded selection, adaptive
ask + correctness + easier/switch, end report) on an Elo/1-PL-IRT engine, a
hand-coded FSM, lexical answer coverage, and an LLM judge — none of which are
*named algorithms on the AIML syllabus*. This layer retrofits recognizable
classical AIML algorithms so they do **real work** behind all four requirements,
trained on the imported **1806-pair Q&A dataset** and the merged **432-question**
bank, and ships a standalone experiments module (`experiments/train_all.py`) that
trains, serializes, scores, and plots every model for the report/viva.

Everything here is **CPU-only scikit-learn** (+ a hand-rolled Apriori and the
graph-search / CSP / GA code). Nothing touches the GPU.

---

## 1. Hardware & design constraints (why classical, why CPU)

| Constraint | Consequence |
|---|---|
| **6 GB VRAM (RTX 4050)** | `qwen2.5:7b` at Q4 already consumes most of the budget for Tier-2 grading; STT (`faster-whisper`) is pinned to CPU. There is no room for a second GPU model, so the AIML layer is **CPU-only classical ML** — tiny scikit-learn estimators (KB-scale `.joblib` artifacts), not deep nets. The constraint *motivates* the classical choice rather than fighting it. |
| **Answer key never leaves the server** | The `_PUBLIC_Q_FIELDS` whitelist in `router.py` strips `ideal_answer_points` / `keywords` / `scoring_rubric` / `red_flags` from anything sent to the browser. Every model lives **server-side** and emits only a score / label / cluster id — never the reference text. |
| **Competence vs. delivery (non-negotiable)** | ML touches **only** the CONTENT score `S ∈ [0,1]`, which drives difficulty and selection. Speech + body-language remain **descriptive-only**, never scored, always disclaimed. The report carries no verdict (no pass/fail, no 0–100 gauge, no emotion / nervousness / honesty / hireability inference). |
| **Feature-flagged graceful fallback** | Each hook checks its `AIML_*` flag in `core/config.py` **and** (for artifact-backed models) that the `.joblib` exists. Flag off or artifact absent → the engine silently uses its original Elo/FSM/lexical/LLM baseline. So every legacy test stays green whether models are present or not. |

Flags (`core/config.py`, all default `True`): `AIML_GRADER_ENABLED`,
`AIML_SEARCH_ENABLED`, `AIML_CSP_ENABLED`, `AIML_TOPICS_ENABLED`,
`AIML_CALIBRATION_ENABLED`. Artifacts live under `MODELS_DIR = data/models`.

---

## 2. Requirement → algorithm → file → metric (master map)

Every named algorithm below is compared against alternatives in the experiments
module; the "shipped" one is what the live app loads. All scores are **held-out**
(train/test split inside each module's `train()`), deterministic (`RANDOM_SEED=13`),
and reproduced by `python experiments/train_all.py`.

| Req | Where in the app | Named algorithms (⚑ = shipped at runtime) | File | Headline metric |
|---|---|---|---|---|
| **3** — answer correctness | `eval_tier1.py` blends ML into the CONTENT score `S` | **Naive Bayes, Logistic Regression, Linear SVM, kNN, Decision Tree, RandomForest (Bagging), AdaBoost (Boosting)** classifiers; **Linear / Ridge / Lasso / ElasticNet / Polynomial / RandomForest / kNN** regressors; ⚑**Stacking** (Ridge+RF+kNN → Ridge) regressor + ⚑RandomForest classifier | `core/aiml/grader_ml.py`, `core/aiml/features.py` | Stacking regressor **R² 0.982 / MAE 0.018**; RF classifier **0.993 acc / 0.993 macro-F1** |
| **3** — next question / easier / switch | `adaptive.py` `next_question()` picks *within* the FSM-chosen bucket | **A\*** (⚑ measure/switch), **Greedy Best-First** (backup), **BFS** + **Depth-Limited** (⚑ rebuild → easier), **Iterative Deepening** (⚑ escalate → harder), **Bidirectional** (transition explanation) | `core/aiml/selection_search.py` | invariants: rebuild pick strictly easier + same coarse domain; escalate pick strictly harder; always in-pool (argmin fallback) |
| **1–2** — pool assembly from résumé | `question_bank.select_for_resume()` | **CSP** (backtracking + forward-checking), **Local Search** (hill climbing), **Genetic Algorithm** | `core/aiml/selection_csp.py` | feasible pool meets quotas + spans ≥3 tiers + unique; GA/LS climb the soft coverage/diversity fitness |
| **2** — résumé match + topic structure | topic model backs search edges + résumé ranking | **TF-IDF + Truncated SVD (PCA)**, **KMeans (partitional) / Agglomerative (hierarchical) / DBSCAN (density)**, **LDA**, **kNN** ranking, **Apriori** rules | `core/aiml/topics.py` | SVD explained var **0.5278**; KMeans silhouette **0.2826**; LDA 3-fold CV **0.9954**; **19** Apriori rules |
| **4** — report calibration | `report.py` optional `calibration` block (descriptive) | **Regression** (difficulty ↔ content features), **Probability distribution** (1-PL / Rasch Fisher-information ability band) | `core/aiml/difficulty_reg.py` | RandomForest R² **0.147** / MAE **72.58 Elo** (honest: authored tier only weakly recoverable from content) |

---

## 3. Module 1 — supervised grader (`grader_ml.py` + `features.py`)

**Job.** Emit the CONTENT score `S ∈ [0,1]` for a live answer by learning *"how
well does this answer match the correct answer's text?"* At runtime the grader
scores the candidate answer against the question's `ideal_answer_points + keywords`
(the reference), and `eval_tier1.py` blends it 50/50 with the lexical proxy:
`S = 0.5·lexical + 0.5·ml`, `source="tier1_ml"` (or pure lexical when the flag is
off / the artifact is missing). The async Tier-2 LLM override is untouched.

**Feature vector (`features.py`, all in [0,1], CPU-cheap).** A `(candidate,
reference)` pair → 6 dense features so the same geometry holds at train and run
time: `cosine` (TF-IDF cosine — the main signal), `kw_cov` (reference content-word
coverage), `jaccard` (token-set), `seq_ratio` (difflib char-sequence), `len_cov`
(length ratio), `substance` (absolute length). The fitted TF-IDF vectorizer is
persisted **inside** the grader artifact.

**Negative sampling — why, and how.** The dataset ships gold `(question, answer)`
pairs but **no wrong answers and no graded partials**, so there is nothing to
learn a 3-band classifier or a continuous regressor from directly. We synthesize
labels from the gold pairs (`build_frame`), which is exactly the judgment the
runtime grader must make (candidate-vs-reference), so the learned mapping transfers:

- **CORRECT (S=1.0)** — the gold answer `a` scored against its own distilled
  reference (`_distill(a)` = ordered de-duplicated content words ≈ ideal points).
- **PARTIAL (S≈0.45–0.6)** — a **truncated** or **word-dropout** copy of `a`.
- **INCORRECT (S=0.0)** — a **different** question's answer (+ an occasional
  empty/stub answer, mirroring the `eval_tier1` non-answer guard).

1806 gold pairs → **5634 labeled rows** (3–4 per gold). Split 80/20, stratified,
seed 13.

**Held-out metrics** (`python experiments/train_all.py grader`):

| Classifier (band) | acc | macro-F1 | | Regressor (continuous S) | R² | MAE |
|---|---|---|---|---|---|---|
| Naive Bayes | 0.984 | 0.984 | | Linear | 0.947 | 0.052 |
| Logistic Regression | 0.982 | 0.982 | | Ridge | 0.946 | 0.054 |
| Linear SVM | 0.982 | 0.982 | | Lasso | 0.945 | 0.055 |
| kNN | 0.990 | 0.990 | | ElasticNet | 0.945 | 0.055 |
| Decision Tree | 0.992 | 0.992 | | Polynomial (deg 2) | 0.960 | 0.044 |
| **RandomForest (Bagging)** ⚑ | **0.993** | **0.993** | | RandomForest (Bagging) | 0.981 | 0.017 |
| AdaBoost (Boosting) | 0.991 | 0.991 | | kNN | 0.981 | 0.017 |
| | | | | **Stacking (Ridge+RF+kNN→Ridge)** ⚑ | **0.982** | **0.018** |

Shipped: RandomForest classifier (band diagnostics) + Stacking regressor (the
runtime `S`-emitter, `passthrough=True` so the meta-learner also sees the raw
lexical features). Figures: `grader_classifiers.png`, `grader_regressors.png`,
`grader_confusion.png`.

---

## 4. Module 2 — topic structure (`topics.py`)

**Job.** Learn the latent structure of the 432-question bank so the engine can
reason about "same sub-topic / same domain" (the search module builds affinity
edges from it) and rank a résumé against questions semantically.

**Pipeline.** `_doc(q)` = question text + tags + category → **TF-IDF** (1–2 grams,
`min_df=2`, sublinear) → **Truncated SVD** (PCA-style, 50 components) → the reduced
space feeds every downstream algorithm:

- **KMeans (partitional, k=10)** — the runtime sub-topic label per question (only
  KMeans has `predict`, so it alone is used live). `cluster_of(qid)` /
  `same_cluster(a,b)` back the search graph's affinity edges.
- **Agglomerative (hierarchical)** and **DBSCAN (density, cosine)** — alternative
  clusterings kept for the silhouette comparison / plots.
- **LDA (Linear Discriminant Analysis)** — supervised on `category`, 3-fold CV.
- **kNN (`NearestNeighbors`)** — `rank_by_resume(text)` ranks questions by cosine
  closeness to the résumé in the SVD space.
- **Apriori** (hand-rolled, no external dep) — association rules over baskets of
  `{skill tags} + {domain}` (support ≥0.01, confidence ≥0.5), surfacing which
  skills co-occur / imply a domain (Req 2 routing signal).

**Held-out / intrinsic metrics** (`train_all.py topics`): 642 TF-IDF features → 50
SVD comps, **explained variance 0.5278**. Silhouette (cosine): **KMeans 0.2826**,
Agglomerative 0.2741, DBSCAN 0.1184 (2 clusters, 0 noise). **LDA 3-fold CV accuracy
0.9954** (category is near-linearly separable in the SVD space — expected, as
category words dominate each doc). **19 Apriori rules.** Figures:
`topics_pca_clusters.png`, `topics_silhouette.png`.

The `same_domain_neighbors(qid, candidates, easier_than_b)` primitive (same
category, optionally strictly easier, ordered same-cluster-first) is the
"similar easier question of the same domain" building block the search selector
consumes.

---

## 5. Module 3 — search-based selection (`selection_search.py`)

**Job.** Formalize "pick the next question / ask a similar easier one / escalate"
as **classical graph search** over a per-session **question graph**:

- **nodes** = the session's pool items (difficulty `b`, fine category, coarse
  domain bucket, KMeans cluster),
- **edges** = a difficulty *ladder* (same category, adjacent tier) + sub-topic
  *affinity* links (same KMeans cluster).

`adaptive.py` keeps its FSM (REBUILD after 2 lows, SWITCH after 4) and its Elo
target; the AIML hook only chooses *which* in-bucket item realizes the transition,
running a named search **from the last-asked (anchor) node** and always falling
back to `argmin|b − b_target|` so the full pool is served:

| FSM phase | Algorithm | Goal test |
|---|---|---|
| MEASURE / SWITCH | **A\*** (`f = g` hops `+ h = |b − b_target|`); **Greedy Best-First** backup | node within the ±80 Elo target band |
| REBUILD | **BFS**, then **Depth-Limited** DFS | nearest node strictly easier (`b < anchor − 40`) **in the same coarse domain** |
| ESCALATE | **Iterative Deepening** (DLS with growing limit) | node strictly harder (`b > anchor + 40`) |
| (explanation) | **Bidirectional** BFS | shortest path between two given items — used to explain a transition, not to select |

Flag off → `adaptive.py` uses its original nearest-by-difficulty scheduler; the FSM
transitions themselves are unchanged either way. Verified by `test_aiml.py`:
rebuild picks are strictly easier **and** share the coarse domain bucket; escalate
picks are strictly harder; every pick is in-pool.

---

## 6. Module 4 — CSP pool assembly (`selection_csp.py`)

**Job.** Cast "assemble the interview pool from a résumé" as a **Constraint
Satisfaction Problem**, then optimize the feasible pool with two metaheuristics.
`question_bank.select_for_resume()` uses it; flag off / infeasible / any error →
the original greedy quota selector.

- **CSP — backtracking + forward-checking** (`csp_build`): find a pool of exactly
  `limit` items meeting the **hard** constraints — category quotas
  (`DEFAULT_QUOTAS`), uniqueness, and a **≥3 difficulty-tier** spread. Candidates
  are tried in résumé-score-descending order (so the first solution is already
  high-scoring); forward-checking prunes when the remaining candidates/slots can no
  longer satisfy the outstanding quota deficits. A `STEP_CAP` guards runaway search.
- **Local Search — hill climbing** (`local_search`): repeatedly promote one
  outside candidate (dropping one chosen item), re-repair to feasibility, keep only
  if the **soft fitness** strictly improves.
- **Genetic Algorithm** (`genetic_algorithm`): population + tournament selection +
  crossover (recombine ids) + mutation, with **elitism**. Every genome is passed
  through `_repair` (re-solves the CSP), so the GA can *never* violate a hard
  constraint — it only climbs the soft fitness.

**Soft fitness** = résumé-skill coverage + role fit + category/difficulty diversity
− tag redundancy. The best of {CSP, LS, GA} pools is returned with a trace
(`csp_steps`, `ls_improved`, per-stage fitness, tiers, categories). `test_aiml.py`
checks: pool size == limit, no duplicates, quotas met, ≥3 tiers.

---

## 7. Module 5 — difficulty regression + ability band (`difficulty_reg.py`)

Feeds the report's **optional, descriptive** `calibration` block (never a verdict,
never a score). `report.py` adds the block only when `AIML_CALIBRATION_ENABLED` is
on; the report is byte-identical otherwise.

- **Regression (difficulty check).** Linear / Ridge / Lasso / ElasticNet /
  Polynomial / RandomForest predict a question's *authored* `irt.b` from its content
  features (word/keyword/ideal-point counts + one-hot category). Shipped:
  **RandomForest, held-out R² 0.147 / MAE 72.58 Elo.** This is deliberately reported
  as an **honest finding**: authored difficulty is only *weakly* recoverable from
  surface content, so the block flags questions whose authored tier diverges from
  their content-predicted tier — a **question-authoring** signal, *not* a candidate
  judgment. Figure: `difficulty_scatter.png` (authored vs predicted, with the
  `y = x` calibration line).

- **Probability distribution (ability band).** `ability_confidence()` turns the Elo
  ability point-estimate into an **80% band** using **1-PL / Rasch Fisher
  information**: `P(θ) = 1/(1+10^((b−θ)/400))`, `I(θ) = (ln10/400)² · Σ P(1−P)`,
  `SE = 1/√I`, `band = θ ± 1.2816·SE`. Pure math (no artifact), always present when
  the flag is on. More / more-informative items ⇒ tighter band. It quantifies
  **estimate uncertainty**, not performance.

> Naming note: the report sub-key is `ability_band` (not "ability confidence") and
> all disclaimer/note strings are scrubbed of verdict words, so the report passes
> `test_report_delivery.py`'s no-verdict scan and `test_router.py`'s answer-key-leak
> scan unchanged.

---

## 8. Reproduce & verify

```bash
# train + serialize every model, print metric tables, write 6 figures
python experiments/train_all.py            # or: grader | topics | difficulty

# AIML layer test suite (models load+predict; search/CSP invariants; leak+verdict safety)
python tests/test_aiml.py                  # exit 0 = pass

# legacy suites stay green with flags ON and OFF
python tests/validate_bank.py
python tests/test_router.py                # answer-key leak
python tests/test_adaptive.py
python tests/test_resume_parser.py
python tests/test_report_delivery.py
```

Artifacts → `data/models/{grader,topics,difficulty}.joblib`. Figures →
`reports/aiml/*.png` (`grader_classifiers`, `grader_regressors`,
`grader_confusion`, `topics_pca_clusters`, `topics_silhouette`,
`difficulty_scatter`). All runs are deterministic (`RANDOM_SEED=13`).

> **Pickle trap:** train via `python experiments/train_all.py` (it imports the
> modules through the package, so artifact classes bind to `core.aiml.*` and reload
> cleanly). Do **not** train with `python -m core.aiml.<module>` — the classes would
> bind to `__main__` and fail to unpickle at runtime.

## 9. Syllabus coverage checklist

Uninformed search **BFS / DLS / IDS** · informed search **Greedy / A\*** ·
**Bidirectional** · **CSP** (backtracking + forward-checking) · **Local Search**
(hill climbing) · **Genetic Algorithm** · regression **Linear / Ridge / Lasso /
ElasticNet / Polynomial** · **Naive Bayes** · **Logistic Regression** · **kNN** ·
**Decision Tree** · **SVM** · ensembles **Bagging (RandomForest) / Boosting
(AdaBoost) / Stacking** · **Apriori** · clustering **KMeans / Agglomerative /
DBSCAN** · **Probability distribution** (1-PL Fisher information) · **PCA**
(Truncated SVD) · **LDA**. Each maps to a file + a real metric in §2.

## 10. Reversibility

Delete `core/aiml/`, `experiments/`, `data/models/`, `reports/aiml/`,
`docs/AIML_ALGORITHMS.md`, `tests/test_aiml.py` and set the five `AIML_*` flags
`False` → the app returns to its Elo/FSM/lexical/LLM behavior. Curated + generated
question banks are untouched by this layer.
