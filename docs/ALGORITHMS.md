# PLUTO vProctor — Hand-Implemented Algorithms Reference

This document catalogs every hand-written algorithm implemented in PLUTO vProctor under `backend/app/algorithms/`, as required by `docs/spec/06-algorithms.md`.

All algorithms are fully documented, strictly typed, self-contained, tested against reference baselines, and benchmarked.

---

## Algorithms Summary Table

| # | Algorithm | Module | Time Complexity | Space Complexity | Where Used in PLUTO |
|---|---|---|---|---|---|
| 1 | **Trie (Prefix Tree)** | `trie.py` | Insert: $O(L)$, Search: $O(L)$, Prefix: $O(P + N)$ | $O(\Sigma \cdot L \cdot N)$ | Skill & keyword autocomplete in UI; matching skills extracted from resume against taxonomy |
| 2 | **Levenshtein Distance** | `edit_distance.py` | $O(M \cdot N)$ | $O(M \cdot N)$ (or $O(\min(M,N))$) | Fuzzy skill matching against job descriptions; speech recognition filler-word variation matching |
| 3 | **KMP (Knuth-Morris-Pratt)** | `string_match.py` | $O(N + M)$ | $O(M)$ failure table | Exact phrase matching in speech transcripts; scanning filler phrases ("you know", "kind of") |
| 4 | **Rabin-Karp** | `string_match.py` | $O(N + M)$ avg, $O(NM)$ worst | $O(1)$ | Multi-pattern or rolling hash transcript search for prohibited phrases / keywords |
| 5 | **Binary Min-Heap (Top-K)** | `heap_topk.py` | Push/Pop: $O(\log K)$, Selection: $O(N \log K)$ | $O(K)$ | Selecting top-$K$ most relevant questions from thousands of candidate Q&A records |
| 6 | **Merge Sort** | `sorting.py` | $O(N \log N)$ worst/avg/best (stable) | $O(N)$ auxiliary | Stable ranking of questions; chronologically ordering proctoring violation events |
| 7 | **Quick Sort (3-way partition)** | `sorting.py` | $O(N \log N)$ avg, $O(N^2)$ worst | $O(\log N)$ stack | In-place fast sorting of candidate metric lists and feature score vectors |
| 8 | **Binary Search** | `searching.py` | $O(\log N)$ | $O(1)$ | Locating proctoring events near timestamps ($O(\log N)$ seek); cutoff threshold lookups |
| 9 | **0/1 Knapsack (DP)** | `knapsack.py` | $O(N \cdot W)$ where $W = \text{budget}$ | $O(N \cdot W)$ | Selecting optimal combination of questions maximizing score while fitting interview time budget |
| 10 | **Interval Merging** | `interval_ops.py` | $O(N \log N)$ | $O(N)$ | Merging overlapping look-away / absence proctoring violations; timeline event compaction |
| 11 | **Sliding Window + EMA + Kalman** | `sliding_window.py` | $O(1)$ per frame update | $O(W)$ window | Gaze look-away detection; head motion estimation; smoothing noisy per-frame MediaPipe signals |
| 12 | **TF-IDF + Cosine Similarity** | `similarity.py` | Fit: $O(D \cdot T)$, Transform: $O(T)$ | $O(V + D)$ | Resume-to-job matching; keyword overlap; answer-to-expected similarity scoring |
| 13 | **BM25 (Okapi BM25)** | `bm25.py` | Fit: $O(D \cdot T)$, Score: $O(T_q \cdot \text{df})$ | $O(V + D)$ | Ranked retrieval of question-answer pairs matching candidate skillset; hybrid evaluation feature |
| 14 | **MinHash & LSH** | `minhash.py` | Signature: $O(S \cdot H)$, Compare: $O(H)$ | $O(H)$ per doc | Cross-split deduplication of questions between `data/` and `data1/` to prevent data leakage |
| 15 | **Maximal Marginal Relevance (MMR)** | `mmr.py` | $O(K \cdot N)$ | $O(N)$ | Selecting diverse question sets avoiding redundant questions on identical subtopics |
| 16 | **RAKE Keyword Extraction** | `keyword_extraction.py` | $O(N_{\text{words}})$ | $O(V_{\text{words}})$ | Extracting key terms from job descriptions and Q&A answers for rubric generation |
| 17 | **Laplace Smoothing & Normalization** | `smoothing.py` | $O(V)$ | $O(V)$ | Smoothing Naive Bayes word likelihoods for domain classification; robust score normalization |

---

## Verification & Testing

All algorithm implementations are accompanied by comprehensive unit tests located in `backend/tests/algorithms/`:

- `test_trie.py` — prefix insertion, exact search, starts_with, autocomplete prefix query.
- `test_edit_distance.py` — empty string bounds, substitution costs, fuzzy matching against rapidfuzz.
- `test_string_match.py` — KMP and Rabin-Karp edge cases, multiple occurrences, empty patterns.
- `test_heap_topk.py` — heap invariant, min-heap push/pop matches `heapq`, top-k selection.
- `test_sorting.py` — merge sort stability, quick sort pivot choices, randomized sorting tests.
- `test_searching.py` — exact match, left/right bound insertion, nearest timestamp lookup.
- `test_knapsack.py` — value maximization, capacity constraint adherence, reconstruction.
- `test_interval_ops.py` — disjoint intervals, complete overlaps, adjacent merges, duration sums.
- `test_sliding_window.py` — rolling mean, variance, exponential moving average, Kalman filter.
- `test_similarity.py` — TF-IDF computation, zero division protection, sparse cosine similarity.
- `test_bm25.py` — term saturation $k_1$, length penalization $b$, scoring ordering.
- `test_minhash.py` — shingling, Jaccard similarity estimation, threshold deduplication.
- `test_keyword_extraction.py` — RAKE word degree / frequency scoring, phrase extraction.

**Status:** 83 / 83 unit tests passing (`pytest backend/tests/algorithms`).
**Benchmarks:** Run via `python scripts/benchmark_algorithms.py`.
