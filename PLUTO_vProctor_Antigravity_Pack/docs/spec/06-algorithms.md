<!-- Spec file for PLUTO vProctor. Section numbers (2B, 5.3, ...) refer to the files in docs/spec/. -->

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
