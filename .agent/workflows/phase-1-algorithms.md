---
description: PLUTO Phase 1: hand-written algorithms library with tests and benchmarks
---

# Phase 1: Algorithms library

Read: `docs/spec/06-algorithms.md`.

1. Implement every algorithm in the table inside `backend/app/algorithms/` (Trie, Levenshtein, KMP, Rabin-Karp, binary min-heap top-K, merge sort, quick sort, binary search, 0/1 knapsack, MMR, interval merging, sliding window + EMA/Kalman, TF-IDF/cosine, BM25, MinHash/LSH, RAKE-style keyword extraction).
2. Each file: docstring with complexity, type hints, no dependency on the rest of the app.
3. pytest for each, cross-checking against reference implementations (`heapq`, `sorted`, `bisect`, `rapidfuzz`, `datasketch` where useful).
4. `scripts/benchmark_algorithms.py`: custom vs built-in timings printed as a table.
5. Start `docs/ALGORITHMS.md` (what each algorithm is, complexity, where the app uses it).

Acceptance: `pytest backend/tests/algorithms` passes; benchmark script runs.
