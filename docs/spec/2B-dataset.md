<!-- Spec file for PLUTO vProctor. Section numbers (2B, 5.3, ...) refer to the files in docs/spec/. -->

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
