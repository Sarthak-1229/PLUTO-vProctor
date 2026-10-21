"""Benchmark hand-written algorithms against Python built-ins and C-extensions.

Runs benchmarks for:
1. Trie vs str.startswith / set
2. Levenshtein vs rapidfuzz
3. KMP / Rabin-Karp vs str.find
4. Binary min-heap top-K vs heapq.nlargest
5. Merge sort & Quick sort vs sorted() (Timsort)
6. Binary search vs bisect
7. TF-IDF & Cosine vs scikit-learn
"""
import sys
import time
import random
import bisect
import heapq
from pathlib import Path

# Ensure workspace root is in path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.app.algorithms.trie import Trie
from backend.app.algorithms.edit_distance import levenshtein
from backend.app.algorithms.string_match import kmp_search, rabin_karp_search
from backend.app.algorithms.heap_topk import top_k
from backend.app.algorithms.sorting import merge_sort, quick_sort
from backend.app.algorithms.searching import binary_search
from backend.app.algorithms.similarity import TFIDFVectorizer, cosine_similarity

try:
    from rapidfuzz.distance import Levenshtein as rapid_lev
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

try:
    from sklearn.feature_extraction.text import TfidfVectorizer as SklearnTFIDF
    from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


def time_fn(fn, *args, repeat=10, **kwargs):
    start = time.perf_counter()
    for _ in range(repeat):
        res = fn(*args, **kwargs)
    elapsed = (time.perf_counter() - start) / repeat
    return elapsed * 1000.0  # in ms


def main():
    print(f"\n{'='*75}")
    print(f"{'PLUTO vProctor: Algorithm Benchmarks':^75}")
    print(f"{'='*75}\n")

    results = []

    # 1. Edit distance (Levenshtein)
    s1 = "convolutional neural network architecture"
    s2 = "recurrent neural network architectures"
    t_custom_lev = time_fn(levenshtein, s1, s2, repeat=50)
    if HAS_RAPIDFUZZ:
        t_ref_lev = time_fn(rapid_lev.distance, s1, s2, repeat=50)
        ref_name = "rapidfuzz (C++)"
    else:
        t_ref_lev = 0.0
        ref_name = "N/A"
    results.append(("Levenshtein Distance", f"{t_custom_lev:.3f} ms", f"{t_ref_lev:.4f} ms ({ref_name})"))

    # 2. String search (KMP / Rabin-Karp vs str.find)
    text = "the quick brown fox jumps over the lazy dog and the fox is very sly " * 100
    pattern = "very sly"
    t_kmp = time_fn(kmp_search, text, pattern, repeat=50)
    t_rk = time_fn(rabin_karp_search, text, pattern, repeat=50)
    t_builtin_find = time_fn(str.find, text, pattern, repeat=50)
    results.append(("String Search (KMP)", f"{t_kmp:.3f} ms", f"{t_builtin_find:.4f} ms (str.find)"))
    results.append(("String Search (Rabin-Karp)", f"{t_rk:.3f} ms", f"{t_builtin_find:.4f} ms (str.find)"))

    # 3. Min-Heap Top-K vs heapq.nlargest
    random.seed(42)
    data = [(random.random(), f"item_{i}") for i in range(5000)]
    t_custom_topk = time_fn(top_k, data, 10, repeat=30)
    t_heapq_topk = time_fn(heapq.nlargest, 10, data, repeat=30)
    results.append(("Top-K Selection (K=10, N=5k)", f"{t_custom_topk:.3f} ms", f"{t_heapq_topk:.3f} ms (heapq.nlargest)"))

    # 4. Sorting (Merge Sort, Quick Sort vs Timsort)
    sort_data = [random.randint(0, 10000) for _ in range(2000)]
    t_merge = time_fn(merge_sort, sort_data.copy(), repeat=20)
    t_quick = time_fn(quick_sort, sort_data.copy(), repeat=20)
    t_timsort = time_fn(sorted, sort_data, repeat=20)
    results.append(("Merge Sort (N=2000)", f"{t_merge:.3f} ms", f"{t_timsort:.4f} ms (Timsort C)"))
    results.append(("Quick Sort (N=2000)", f"{t_quick:.3f} ms", f"{t_timsort:.4f} ms (Timsort C)"))

    # 5. Binary Search vs bisect
    sorted_arr = list(range(10000))
    target = 7432
    t_custom_bin = time_fn(binary_search, sorted_arr, target, repeat=1000)
    t_bisect = time_fn(bisect.bisect_left, sorted_arr, target, repeat=1000)
    results.append(("Binary Search (N=10k)", f"{t_custom_bin * 1000:.2f} µs", f"{t_bisect * 1000:.2f} µs (bisect C)"))

    # 6. Trie Autocomplete vs linear startswith
    words = [f"skill_keyword_{i}" for i in range(1000)] + ["python", "pytorch", "pytest", "pydantic"]
    trie = Trie()
    for w in words:
        trie.insert(w)
    prefix = "py"
    t_trie = time_fn(trie.autocomplete, prefix, repeat=500)
    def linear_match(p, corpus):
        return [w for w in corpus if w.startswith(p)]
    t_linear = time_fn(linear_match, prefix, words, repeat=500)
    results.append(("Trie Autocomplete", f"{t_trie * 1000:.2f} µs", f"{t_linear * 1000:.2f} µs (list comp)"))

    # 7. TF-IDF + Cosine Similarity
    docs = [
        "python developer with experience in django fastapi sql rest api",
        "machine learning engineer deep learning pytorch tensorflow computer vision",
        "frontend react developer typescript javascript tailwind vite web development",
        "data analyst sql python pandas power bi statistics tableau reporting"
    ]
    vec = TFIDFVectorizer()
    vec.fit(docs)
    def custom_transform_all(corpus):
        return [vec.transform(d) for d in corpus]
    mat = custom_transform_all(docs)
    t_custom_tfidf = time_fn(custom_transform_all, docs, repeat=50)
    if HAS_SKLEARN:
        sk_vec = SklearnTFIDF()
        sk_vec.fit(docs)
        t_sk_tfidf = time_fn(sk_vec.transform, docs, repeat=50)
        sk_name = "sklearn"
    else:
        t_sk_tfidf = 0.0
        sk_name = "N/A"
    results.append(("TF-IDF Vectorization", f"{t_custom_tfidf:.3f} ms", f"{t_sk_tfidf:.3f} ms ({sk_name})"))

    # Print Table
    col_w = [30, 18, 26]
    header = f"{'Algorithm':<{col_w[0]}} | {'Custom (Handmade)':<{col_w[1]}} | {'Built-in / Reference':<{col_w[2]}}"
    sep = "-" * len(header)
    print(header)
    print(sep)
    for name, custom_t, ref_t in results:
        print(f"{name:<{col_w[0]}} | {custom_t:<{col_w[1]}} | {ref_t:<{col_w[2]}}")
    print(sep)
    print("\nBenchmark completed successfully.")


if __name__ == "__main__":
    main()
