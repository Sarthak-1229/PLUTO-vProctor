# PROMPT FOR CLAUDE CODE: Build "PLUTO vProctor" from scratch

You are a senior AI/ML engineer. Build the complete project described below from scratch in an empty directory called `pluto-vproctor/`. **I already own a real question-and-answer dataset** (described in section 2B). Use it as the single source of truth for interview questions and reference answers. Do NOT invent or hand-write a question bank. Work autonomously, phase by phase. After each phase: run it, test it, fix errors, `git commit`, then continue. Do not stop to ask questions; where something is ambiguous, pick the sensible default, record it in `docs/DECISIONS.md`, and move on. This is an academic AIML project, so the AI/ML algorithms and the classic search and sorting algorithms must be visible, implemented by hand where stated, and documented.

---

## 1. Product summary

PLUTO vProctor is a local, privacy-friendly AI mock-interview and proctoring web app.

1. The candidate selects a job role or company and uploads a resume (PDF/DOCX).
2. The system parses skills, experience and education, and scores the resume against the job profile.
3. If the resume fails the job requirements, the candidate is marked **"Rejected at screening"** but is **still allowed to take the interview**.
4. The system filters the question dataset using the job profile plus resume, and asks only the necessary questions.
5. An AI interviewer shows each question on screen and speaks it aloud. The candidate sees their own live video and must sit at a proper distance (desktop/laptop webcam).
6. During the interview the system checks eye contact and body movement live. If the candidate looks away, an on-screen alert is shown, and score is deducted for looking away and for excessive movement.
7. The whole interview is recorded. Afterwards, **video analysis and audio analysis run simultaneously (in parallel)**.
8. Audio is checked for pauses and filler words ("umm", "ahh", "uh", "like", "you know"); a confidence score is computed and points are deducted.
9. At the end the candidate gets a score summary, what to improve, and a **timeline of every deduction with its mm:ss position in the recording**, clickable to seek the video.

---

## 2. HARD CONSTRAINTS (read carefully)

- **Everything runs locally.** No paid cloud APIs. No OpenAI/Anthropic/Google API calls inside the app.
- **Local LLM: `qwen2.5:3b` served by Ollama** (`http://localhost:11434`). The dev machine has **only 6 GB VRAM**, so:
  - Never load more than one GPU model at a time. Use a `GPUScheduler` (a semaphore/lock) so Ollama and Whisper never run on the GPU simultaneously.
  - Whisper: use `faster-whisper` with model `small` (or `base`), `compute_type="int8"`. Make device configurable (`cuda` or `cpu`), default `cpu` while the LLM is loaded, with auto-fallback.
  - Sentence embeddings: `sentence-transformers/all-MiniLM-L6-v2` on **CPU**.
  - MediaPipe runs on CPU.
  - Set Ollama `keep_alive` low (e.g. `30s`) so VRAM frees after use, and `num_ctx` to 4096 max.
- The 3B model is weak. So: keep prompts short and structured, ask for **JSON output** (`format: "json"` in the Ollama API), validate with Pydantic, retry once on invalid JSON, and fall back to deterministic algorithmic logic if the LLM fails. **The LLM must never be the only thing deciding a score.** Core scoring is algorithmic; the LLM assists (explanations, follow-ups, answer-relevance rubric).
- Python 3.10+, FastAPI backend, React (Vite) frontend, SQLite via SQLAlchemy. Windows-friendly (no bash-only assumptions; provide both `.bat` and `.sh` run scripts).
- Browser TTS (`window.speechSynthesis`) is used for the interviewer voice (zero VRAM).
- **Use my real datasets** (section 2B). No synthetic question bank. Synthetic data is allowed only for resume–job pairs (the dataset has none) and must be labelled as synthetic in the docs.

---

## 2B. DATASET (real data I already have; build everything around it)

**Location (I will copy my folders into the repo root before you start):**

```
pluto-vproctor/datasets/
├─ data/   train.json(l)  val.json(l)  test.json(l)
└─ data1/  train.json(l)  val.json(l)  test.json(l)
```

**Observed format.** I inspected one file (`test.jsonl`, 272 rows). It is **JSON Lines**, one object per line, with exactly two string fields:

```json
{"question": "What is Canary Deployment?", "answer": "New versions are released to a small subset of users first to validate performance before a full rollout."}
```

Measured facts about that file (use them as design inputs, but re-measure on the full data):
- Questions are short (mean about 8 words, max 16). Answers are short and dense (mean about 17.5 words, range 11 to 27), single line, no newlines.
- No duplicate questions inside the file.
- **There is no metadata at all**: no topic, skills, difficulty, job role, question type or id. All of that must be derived by the ingestion/enrichment pipeline below.
- Phrasing is dominated by "What is ...", "Explain the ...", "Describe the ...", with a few "How does ...", "Implement a ...", "Design a ...", "Build a ...".
- The content is broad technical interview material: security (very frequent), cloud/AWS, DevOps/SRE (Docker, Kubernetes, Istio, ELK, canary deployments, SLOs), databases, OOP and design patterns, data structures and algorithms, data science/ML (data drift, confusion matrix, computer vision), bioinformatics (variant calling, reference genome, pathway analysis, indels), blockchain (51% attack), web/CSS (viewport meta tag), Java, operating systems (Banker's algorithm).

**The other files (`train`, `val`, `test` in both `data/` and `data1/`) may differ in extension (`.json` vs `.jsonl`), in schema, or in size.** So the loader must be defensive.

### 2B.1 `scripts/ingest_datasets.py` (build this first, Phase 2)
1. Walk `datasets/data*/` and load every `train|val|test` file. Auto-detect the format per file: JSONL, a JSON array, or a JSON object wrapping a list (`{"data":[...]}`). Handle UTF-8 with BOM.
2. Auto-detect field names with aliases (`question|prompt|instruction|q|input`, `answer|response|output|a|completion`). If a file has extra fields (topic, category, difficulty, id, tags, role, ...), **keep them** and carry them through; they override the derived metadata. Log a per-file **schema report** (rows, keys, missing/empty fields, length stats) to `docs/DATASET_REPORT.md`.
3. Clean: strip, collapse whitespace, normalise unicode quotes, drop rows with an empty question or answer, drop rows that are not English if detectable.
4. **Deduplicate across ALL files** (data and data1, all splits):
   - exact match on the normalised question (lowercase, no punctuation);
   - near-duplicates using **MinHash/LSH or Jaccard over word 3-shingles** (implement the shingling + MinHash yourself, cross-check against `datasketch` or `rapidfuzz` in a test) and a question-embedding cosine threshold (>= 0.92) as a second check;
   - when the same question appears in several splits, **keep it only in the highest-priority split in the order test > val > train** to prevent train/test leakage. Report how many rows were removed and why.
5. Assign each surviving row a stable id (`q_` + short hash of the normalised question) and store `source_folder` (`data` or `data1`) and `split`.
6. Output `backend/app/data/processed/qa_clean.jsonl` plus `docs/DATASET_REPORT.md` containing: counts per folder/split before and after cleaning and dedup, length distributions, most frequent question openings, sample rows, and any anomalies.

### 2B.2 `scripts/enrich_questions.py` (Phase 2, runs after ingest; fully offline, no LLM required)
Because the data has no metadata, derive it with classical NLP/ML and write `backend/app/data/processed/questions.json`:

| Derived field | How to derive it |
|---|---|
| `type` | Rule-based from the opening pattern: `definition` (What is / What are), `explain` (Explain / Describe / Discuss), `how_why` (How/Why), `compare` (difference between / vs / compare), `scenario` (When would / what happens if), `coding` (Implement / Write / Find / Build / Design / Create ...). Interview mapping: `definition` and `explain` are warm-up/core, `how_why`/`compare`/`scenario` are deeper, `coding` needs a screen. |
| `spoken_ok` | `False` for `coding` questions and any question that needs writing code, a diagram or a long design. The **voice interview must only ask `spoken_ok=True` questions**; keep the others in the DB for a future coding round. |
| `skills[]` | Match the question and answer text against `skills_taxonomy.json` using the Trie + fuzzy + embedding pipeline from section 5.2. **Build the taxonomy from the data**: extract candidate terms (capitalised terms, acronyms, noun phrases, frequent bigrams via TF-IDF/RAKE), keep the top ~500, then manually curate a seed list (AWS, Docker, Kubernetes, Istio, ELK, Java, CSS, SQL, Zero Trust, IDS/IPS, SOAR, CAP theorem...) and write it to `skills_taxonomy.json`. |
| `domain` | Assign one of about 12 curated domains: Security, Cloud, DevOps/SRE, Databases, Data Science/ML, Bioinformatics, Blockchain, Web Development, OOP/Software Design, Data Structures and Algorithms, Operating Systems/Networks, General. Use a **seeded keyword scorer + embedding-centroid nearest neighbour**, then fit a **Multinomial Naive Bayes and Logistic Regression** domain classifier on these pseudo-labels (train split only), tune on val, report macro-F1 on test. Use the classifier for rows where the rules are uncertain. |
| `cluster_id` | **K-Means** over MiniLM embeddings of `question + answer`. Pick k by silhouette score on val (try roughly 15 to 60). Label each cluster with its top TF-IDF terms. Use clusters for diversity and for discovering domains the curated list missed. Save a 2-D PCA/UMAP scatter to `docs/figures/`. |
| `difficulty` (1 to 3) | Heuristic score from: answer length, mean IDF of rare terms in the question, presence of words like "trade-offs", "architecture", "strategy", "zero trust", "consensus", and number of acronyms. Convert to terciles. Optionally calibrate with the local LLM behind a `--use-llm` flag (off by default). Document it as an approximation. |
| `expected_keywords[]` | Top 4 to 8 content terms from the reference **answer** (RAKE or TF-IDF, stop-words removed, lemmatised). Used for keyword-coverage scoring. |
| `ideal_answer_summary` | The dataset's `answer`, unchanged. |
| `est_seconds` | Estimate by type and difficulty (for example definition 45 s, explain 70 s, how/why 90 s, scenario 100 s). Used by the knapsack time budget. |
| `embedding` | Store MiniLM vectors for question and answer in a `.npy` file keyed by id (CPU, batch 64). Do not store them in SQLite JSON. |

Print a **coverage table**: questions per domain, per type and per difficulty, and per split. Fail loudly if any job profile (section 5.1) ends up with fewer than 25 usable questions, and fix the job's domain mapping instead of inventing questions.

### 2B.3 How each split is used (strict rules)
- **train**: fitting anything: TF-IDF vocabulary, IDF weights, domain classifier, answer-relevance model, K-Means, keyword extractors.
- **val**: choosing hyper-parameters and thresholds (k, similarity cut-offs, score blend weights, difficulty terciles).
- **test**: touched **once**, only by `scripts/evaluate_*.py`, to report final metrics. Never fit or tune on test. The interview itself draws questions from train, val and test pooled (all are valid interview content), but the ML evaluation respects the split.
- If a model needs train-only vocabulary, rebuild the question pool for the interview from the full pool without refitting the evaluation models.

### 2B.4 Dataset-driven ML evaluations (these give the project measurable AIML results)
Because every row is a gold (question, reference answer) pair, build these in `scripts/`:
1. **Domain classifier:** accuracy, macro-F1 and confusion matrix (NB vs Logistic Regression vs embedding+kNN).
2. **Question to answer retrieval:** for each test question, rank all test answers by TF-IDF cosine, BM25 (implement), and MiniLM cosine. Report Recall@1/3/5 and MRR. This validates the embedding model for answer scoring.
3. **Answer-relevance classifier:** build positive pairs (question, its true answer) and negative pairs (question, answer of another question; make **hard negatives** by sampling from the same K-Means cluster or domain). Features: MiniLM cosine, TF-IDF cosine, keyword recall, answer-length ratio, BM25. Fit a Logistic Regression and a Gradient Boosting baseline on train, tune on val, report accuracy, precision, recall, F1, ROC-AUC on test. This model produces the algorithmic part of the answer-quality score (section 5.7).
4. **Resume screening classifier** (synthetic, see section 5.2) with its own F1/confusion matrix.
5. **Question selection quality:** compare random vs relevance-only vs relevance+MMR vs relevance+MMR+knapsack on sample resumes by topic coverage, redundancy (mean pairwise similarity) and total time. Print a table.

---

## 3. Architecture

```
React (Vite) frontend
 ├─ Setup page (job select, resume upload, screening result)
 ├─ Interview page (video, question display + TTS, live alerts, recorder)
 ├─ Processing page (progress polling)
 └─ Report page (scores, summary, deduction timeline, video seek)
        │  REST + WebSocket
FastAPI backend
 ├─ resume_service      (parse + score)
 ├─ question_service    (filter + select + order)
 ├─ interview_service   (session state, follow-ups via LLM)
 ├─ analysis_service    (orchestrates parallel pipelines)
 │    ├─ video_pipeline (MediaPipe: gaze, head pose, body motion)
 │    └─ audio_pipeline (ffmpeg → faster-whisper → pauses/fillers)
 ├─ scoring_engine     (merges all deductions)
 ├─ report_service     (summary via LLM + deterministic fallback)
 └─ llm_client         (Ollama wrapper, JSON mode, retries, GPU lock)
SQLite + local /storage (resumes, recordings, reports)
```

Live checks (gaze/movement alerts) run **in the browser** with MediaPipe Tasks Vision (JS) for low latency and zero backend load. The authoritative scoring is recomputed **server-side after the interview** from the recording using Python MediaPipe, so results are consistent and cannot be spoofed. Both are logged as events with timestamps.

---

## 4. Folder structure to create

```
pluto-vproctor/
├─ datasets/                      # MY real data (copied in by me, read-only, never edited)
│  ├─ data/  (train, val, test)
│  └─ data1/ (train, val, test)
├─ backend/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ config.py
│  │  ├─ db.py, models.py, schemas.py
│  │  ├─ routers/ (jobs.py, resume.py, interview.py, analysis.py, report.py)
│  │  ├─ services/ (resume_service.py, question_service.py, interview_service.py,
│  │  │             analysis_service.py, scoring_engine.py, report_service.py,
│  │  │             answer_eval_service.py, llm_client.py)
│  │  ├─ pipelines/ (video_pipeline.py, audio_pipeline.py)
│  │  ├─ algorithms/ (each file standalone + unit tested)
│  │  │   ├─ trie.py, sorting.py, searching.py, heap_topk.py, knapsack.py,
│  │  │   ├─ string_match.py, edit_distance.py, interval_ops.py,
│  │  │   ├─ similarity.py, bm25.py, minhash.py, mmr.py, smoothing.py,
│  │  │   ├─ sliding_window.py, keyword_extraction.py, ml_models.py
│  │  └─ data/
│  │      ├─ jobs.json                 # hand-written job profiles (the only hand-written data)
│  │      ├─ skills_taxonomy.json      # built from the datasets + curated
│  │      ├─ fillers.json
│  │      └─ processed/ (qa_clean.jsonl, questions.json, embeddings.npy, models/*.joblib)
│  ├─ tests/
│  ├─ scripts/ (ingest_datasets.py, enrich_questions.py, seed_db.py, train_models.py,
│  │            evaluate_domain.py, evaluate_retrieval.py, evaluate_answer_relevance.py,
│  │            evaluate_screening.py, evaluate_selection.py, benchmark_algorithms.py)
│  └─ requirements.txt
├─ frontend/ (Vite + React + Tailwind)
├─ docs/ (ARCHITECTURE.md, ALGORITHMS.md, DATASET_REPORT.md, DECISIONS.md, API.md, REPORT_TEMPLATE.md, figures/)
├─ run_dev.bat, run_dev.sh
└─ README.md
```

---

## 5. Feature specifications

### 5.1 Jobs and data
- **Questions and reference answers come only from my datasets** (section 2B). `questions.json` is produced by `scripts/ingest_datasets.py` and `scripts/enrich_questions.py`; `scripts/seed_db.py` loads it into SQLite. Do not write questions by hand.
- `jobs.json` is the **only hand-written dataset**. Create **at least 12 job profiles** whose `question_domains` map onto the domains found in the real data (Security Analyst, Cloud Engineer, DevOps/SRE Engineer, Backend Developer (Java), Database Administrator, Data Scientist / ML Engineer, Bioinformatics Analyst, Blockchain Developer, Web/Frontend Developer, Software Engineer (OOP + DSA), Network/Systems Engineer, QA/Automation Engineer, ...). Each has: `id, title, company, required_skills[], preferred_skills[], min_experience_years, education_levels[], skill_weights{}, question_domains[], pass_threshold`. Base the skill lists on skills that actually exist in `skills_taxonomy.json`, so every required skill can be linked to real questions.
- Companies: invent 5 to 6 fictional company names so the "select company" flow works; a company simply owns several job profiles.
- `skills_taxonomy.json`: built from the data per section 2B.2 and curated. Aliases are required (for example "k8s" to "kubernetes", "js" to "javascript").
- `fillers.json`: filler words and phrases ("umm", "uh", "ahh", "er", "like", "you know", "I mean", "sort of", "basically", "actually").
- **Synthetic resumes**: because the datasets contain no resumes, `scripts/train_models.py` generates labelled synthetic resume-job pairs for the screening classifier and writes 5 realistic sample resumes (PDF and DOCX) for tests. Mark them as synthetic in all docs.

### 5.2 Resume parsing and scoring
- Extract text: `pdfplumber`/`PyMuPDF` for PDF, `python-docx` for DOCX.
- Section segmentation with regex heading detection (Skills, Experience, Education, Projects).
- **Skills extraction (layered):** (1) Trie / Aho-Corasick-style prefix matching against taxonomy, (2) fuzzy matching with own Levenshtein implementation + `rapidfuzz` for comparison, (3) semantic matching with MiniLM embeddings + cosine similarity for skills not found literally. Normalize via aliases.
- **Experience:** regex + date-range parsing ("Jan 2020 – Mar 2022", "2 years") → total years; merge overlapping date intervals with the interval-merge algorithm so overlaps are not double-counted.
- **Education:** detect degree level (diploma, bachelor, master, PhD) and field via keyword mapping.
- **Scoring (deterministic):**
  `fit = 0.55*skill_score + 0.25*experience_score + 0.20*education_score`
  - `skill_score`: weighted coverage of required skills + 0.5-weight preferred skills, using TF-IDF-weighted cosine similarity between resume skill vector and job skill vector as a secondary signal.
  - `experience_score`: `min(1, years/min_experience)` with a smooth penalty curve.
  - `education_score`: level match.
- Also train a small **Logistic Regression** (scikit-learn) on synthetic labelled resume-job pairs (generated by `train_models.py`) to output a pass probability; show it next to the rule-based score and explain differences in the report (this is the "ML model" part of the screening).
- If `fit < pass_threshold` or any hard requirement is missed: `screening_status = "REJECTED"` with reasons (missing skills, experience gap, education gap) but the UI shows a "Proceed to interview anyway" button.

### 5.3 Question filtering and selection (most algorithm-heavy part)
Candidate pool = `questions.json` entries with `spoken_ok=True` (the real data from section 2B). Pipeline:
1. **Inverted index** (hash map: skill, domain, cluster id -> question ids) for fast candidate retrieval from the job's `question_domains` and required skills.
2. **Relevance score** per question = weighted sum of: overlap with job required/preferred skills, overlap with the candidate's resume skills (boost questions on technologies the candidate lists in projects), embedding cosine similarity between the question and the resume summary, and difficulty fit to experience level (junior: mostly 1 to 2; senior: mostly 2 to 3). Weights live in `config.py` and are tuned on the val split by the selection evaluation (2B.4 item 5).
3. **Top-K via a binary min-heap** (implement manually, verify against `heapq` in tests).
4. **Diversity with MMR (Maximal Marginal Relevance)** using embedding similarity so near-identical questions (the data has many sibling questions, for example several database-security ones) are not asked together. Also cap questions per `cluster_id` and per `domain`.
5. **Time budget with 0/1 Knapsack DP**: choose the subset maximising total relevance within the interview length (default 12 minutes, using `est_seconds`).
6. **Ordering by custom merge sort:** (a) one warm-up question first: a general "Tell me about yourself" prompt built into the app (this one is not from the dataset), (b) `definition`, then `explain`, (c) `how_why`/`compare`/`scenario`, (d) closing question. Within a group sort by relevance then difficulty.
7. **Adaptive follow-ups (LLM + RAG):** after an answer, if the transcript is very short or the answer-relevance score is low, retrieve the 2 nearest dataset Q&A pairs (cosine kNN) and give them to Qwen2.5-3B as grounding to generate **one** short follow-up (max 20 words) as strict JSON. Cap at 3 follow-ups per interview. If the LLM fails, skip the follow-up.
8. Never repeat a question in the same session; record which question ids were asked per candidate so repeated practice sessions rotate the pool.

### 5.4 Interview experience (frontend + WebSocket)
- Pre-check screen: camera + mic permission, face-in-frame guide, **distance check** (face bounding-box width as a % of frame: too close >55%, too far <18%), lighting check (mean brightness), "Start interview" enabled only when OK.
- Interviewer panel shows question text + animated avatar/waveform, TTS speaks the question. Candidate's mic is only evaluated after TTS finishes.
- Controls: "Next question" (or auto-advance after 3 s of detected silence following speech), progress bar, countdown timer per question.
- **Live proctoring in the browser** (MediaPipe Face Landmarker with iris landmarks + Pose Landmarker):
  - Gaze/eye-contact estimate from iris position relative to eye corners + head yaw/pitch from face transformation matrix.
  - If looking away > 2.0 s (sliding window + EMA smoothing), show a red on-screen alert and log an event `{type:"LOOK_AWAY", t_start, t_end, severity}`.
  - Movement: shoulder/nose landmark displacement variance over a 1 s window; excessive movement logs `EXCESSIVE_MOTION`; leaning/slouching logs `POSTURE`; no face → `FACE_MISSING`; multiple faces → `MULTIPLE_FACES`.
  - Live score gauge decreasing as deductions occur.
- Record with `MediaRecorder` (video+audio, webm). Upload in chunks at the end (or stream chunks) to `/api/interview/{id}/recording`. Also send per-question start/end timestamps so each answer can be mapped to the recording.
- Handle tab-switching (`visibilitychange`) as `TAB_SWITCH` event.

### 5.5 Post-interview analysis (parallel)
Use `concurrent.futures.ProcessPoolExecutor` / `asyncio` so these run **simultaneously**:

**Video pipeline (`video_pipeline.py`)**
- Sample frames at ~5 fps with OpenCV; MediaPipe Face Mesh (iris) + Pose.
- Compute per-frame: gaze direction, head yaw/pitch/roll, eye-contact boolean, shoulder/nose displacement, posture angle, face count.
- Smooth with EMA/Kalman; detect continuous violation segments with a **sliding window** and merge adjacent segments with **interval merging**.
- Output: list of events with `t_start, t_end, type, severity` and aggregate stats (eye-contact %, motion index, posture score).

**Audio pipeline (`audio_pipeline.py`)**
- `ffmpeg` extract 16 kHz mono wav.
- `faster-whisper` with `word_timestamps=True`, `vad_filter=False` (VAD removes fillers), and an `initial_prompt` such as "Umm, uh, like, you know, so, I mean..." to encourage keeping fillers in the transcript.
- **Filler detection:** exact match with a hash set, plus multi-word fillers via **KMP** (implement) and compare with **Rabin–Karp**; fuzzy variants ("ummm", "uhhh", "ahm") through Levenshtein distance ≤ 1 against the filler list.
- **Pauses:** gaps between consecutive word timestamps > 1.2 s (mid-answer pause), and response latency > 3 s after the question ends (late start).
- **Pace:** words per minute per answer; flag < 100 or > 180 wpm.
- Optionally compute pitch/energy variability using `librosa` for a "monotone" indicator (low weight).
- Output: transcript with timestamps, events (`FILLER_WORD`, `LONG_PAUSE`, `LATE_START`, `PACE_FAST`, `PACE_SLOW`), and per-answer stats.

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

---

## 6. Required AI/ML + Search/Sort algorithms (implement by hand and document)

Implement these in `backend/app/algorithms/`, each with docstrings (time/space complexity), unit tests, and a section in `docs/ALGORITHMS.md` explaining where it is used in the app. Add `scripts/benchmark_algorithms.py` that benchmarks the custom versions vs the Python built-ins and prints a table.

| Algorithm | Where used |
|---|---|
| Trie (prefix tree) | skill lookup and autocomplete in job/skill search |
| Levenshtein distance (DP) | fuzzy skill and filler word matching |
| KMP and Rabin–Karp | phrase/filler search in transcript |
| Inverted index (hash map) | question retrieval by skill/topic |
| Binary min-heap (Top-K) | pick top K relevant questions |
| Merge sort (stable) and Quick sort | rank questions, order deductions by time |
| Binary search | locate deductions near a video timestamp; threshold lookups |
| 0/1 Knapsack (DP) | choose questions within time budget |
| MMR (greedy) | diverse question selection |
| Interval merging | combine overlapping experience ranges and violation segments |
| Sliding window + EMA/Kalman smoothing | look-away and motion detection |
| TF-IDF + cosine similarity | resume–job matching, answer similarity |
| Sentence embeddings + cosine kNN | semantic skill and question matching |
| K-Means clustering | question topic diversity |
| Logistic Regression (+ optional Naive Bayes baseline) | screening pass/fail probability; compare in the docs |
| Rule-based + LLM hybrid | answer evaluation and summaries |
| MinHash / LSH (Jaccard on word shingles) | near-duplicate removal across `data` and `data1` |
| BM25 (own implementation) | question-to-answer retrieval and answer relevance feature |
| RAKE / TF-IDF keyword extraction | `expected_keywords` and taxonomy building from the dataset |
| Multinomial Naive Bayes + Logistic Regression | domain classification of questions |
| Gradient Boosting (baseline) | answer-relevance classifier comparison |
| kNN retrieval (cosine) | RAG neighbours for follow-up questions |
| PCA / UMAP | cluster visualisation for the report |

Also add a small **evaluation notebook/script** (`scripts/evaluate_screening.py`) reporting accuracy/precision/recall/F1 and a confusion matrix of the screening classifier on a held-out synthetic set, to give the project a measurable ML result.

---

## 7. API (design and document in `docs/API.md`)

- `GET /api/jobs`, `GET /api/jobs/search?q=` (trie-based)
- `POST /api/resume/upload` (multipart: file, job_id) → `{session_id, parsed, fit, screening}`
- `POST /api/interview/{sid}/start` → filtered question list
- `WS /ws/interview/{sid}` → events: `question_started`, `question_ended`, `live_event`, `follow_up`
- `POST /api/interview/{sid}/recording` (upload webm)
- `POST /api/analysis/{sid}/run` → starts parallel pipelines; `GET /api/analysis/{sid}/status` (progress per pipeline)
- `GET /api/report/{sid}` (JSON), `GET /api/report/{sid}/pdf`

---

## 8. Phased build plan (follow in order)

**Phase 0: Setup.** Repo, venv, `requirements.txt`, `package.json`, config, health endpoint, README skeleton, Ollama check script (`ollama pull qwen2.5:3b`, verify the model responds), ffmpeg check, and a check that `datasets/data` and `datasets/data1` exist (print what was found).
**Phase 1: Algorithms library + tests.** All items in section 6 with pytest tests passing (include MinHash and BM25).
**Phase 2: Dataset ingestion and enrichment (section 2B).** `ingest_datasets.py` (schema detection, cleaning, cross-folder dedup, leakage prevention), `enrich_questions.py` (type, spoken_ok, skills, domain, cluster, difficulty, keywords, embeddings), `skills_taxonomy.json`, `jobs.json`, `fillers.json`, `seed_db.py`, and `docs/DATASET_REPORT.md` with the coverage table. **Stop and review the report before continuing; if a job has fewer than 25 questions, fix the mapping.**
**Phase 3: Resume pipeline.** Parser, skill extraction (Trie, fuzzy, embeddings), scoring, synthetic data generation, Logistic Regression screening classifier, evaluation script, screening endpoint, 5 sample resumes.
**Phase 4: Question engine.** Inverted index, heap, MMR, knapsack, ordering, cluster caps, RAG follow-ups; `evaluate_selection.py` comparing strategies; tests with the sample resumes.
**Phase 5: Frontend setup and interview UI.** Setup page, pre-check, interview page with TTS, MediaPipe live proctoring, recorder, upload.
**Phase 6: Analysis pipelines.** Video and audio pipelines, run in parallel, status polling, GPU scheduler. Test with a sample recorded clip (script to generate a synthetic clip if none exists).
**Phase 7: Answer evaluation, scoring, report.** Train and evaluate the answer-relevance model, `answer_eval_service.py`, scoring engine, LLM summary, PDF export, report page with the clickable timeline and reference answers.
**Phase 8: Polish.** Error handling (camera denied, no face, LLM down, dataset file missing), loading states, logging, consent screen + "Delete my data" button, performance tuning for 6 GB VRAM (log peak VRAM), README, docs.
**Phase 9: Project-report support.** `docs/REPORT_TEMPLATE.md`: problem statement, architecture (mermaid), **dataset description with the real numbers from DATASET_REPORT.md**, algorithm explanations with complexity, all evaluation tables (domain, retrieval, answer-relevance, screening, selection), screenshots checklist, limitations and future work.

---

## 9. Quality rules

- Type hints and docstrings everywhere; Pydantic schemas for all API I/O.
- `pytest` coverage for algorithms, scoring engine, parsers; at least one end-to-end test that runs resume → questions → mocked analysis → report.
- Every threshold/weight in `config.py` (no magic numbers in logic).
- Deterministic fallbacks for all LLM calls; log LLM latency and failures.
- Accessibility: keyboard navigable, captions of the spoken question on screen.
- Privacy: all data stays local; add a consent step; store recordings under `/storage/{session_id}` and provide deletion.
- Keep memory in check: stream/read video in chunks, process frames, never load the whole video in RAM.
- Document fairness limits (gaze norms, accents, neurodiversity) in `docs/DECISIONS.md` and make thresholds adjustable in a settings panel.

## 10. Definition of done

0. `python backend/scripts/ingest_datasets.py && python backend/scripts/enrich_questions.py && python backend/scripts/seed_db.py` runs cleanly on my real `datasets/` folders and produces `docs/DATASET_REPORT.md`, with no train/test leakage and every job profile backed by at least 25 real questions.
1. `run_dev.bat` starts backend + frontend; app opens in browser.
2. I can pick a job, upload a resume, see the screening result (including a "rejected but can still interview" flow).
3. I get a filtered, ordered question list and a full spoken interview with live look-away alerts.
4. After the interview, the video and audio pipelines run in parallel and finish, and I see a report with the score breakdown, LLM summary and tips, the reference answer from my dataset for each question, and a deduction timeline where clicking a row seeks the recording to that mm:ss.
5. All tests pass, the benchmark and the five `evaluate_*.py` scripts run on the val/test splits and print their metrics, and the docs are written.

Begin with Phase 0 now. Before coding, print a short plan of the phases, and tell me the exact path where you expect my `datasets/` folders. In Phase 2, first print the schema report for every dataset file you find (they may differ from the sample I described) and adapt the loader to what is really there.
