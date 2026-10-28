"""Evaluate Question-to-Answer retrieval models on the held-out test split.

Implements Section 2B.4 Item 2 of docs/spec/2B-dataset.md:
Compares TF-IDF vs BM25 vs MiniLM embeddings on Recall@1, Recall@3, Recall@5, and MRR.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

# Ensure root in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.app.algorithms.bm25 import BM25
from backend.app.algorithms.similarity import TFIDFVectorizer, cosine_similarity
from backend.app.config import settings

QUESTIONS_JSON = settings.PROCESSED_DATA_DIR / "questions.json"
EMBEDDINGS_NPY = settings.PROCESSED_DATA_DIR / "embeddings.npy"
EMBEDDINGS_IDS = settings.PROCESSED_DATA_DIR / "embeddings_ids.json"


def evaluate_retrieval():
    print("=" * 80)
    print(f"{'PLUTO vProctor: Question-to-Answer Retrieval Evaluation (Test Split)':^80}")
    print("=" * 80)

    if not QUESTIONS_JSON.exists():
        print(f"Error: {QUESTIONS_JSON} does not exist.")
        sys.exit(1)

    with open(QUESTIONS_JSON, "r", encoding="utf-8") as f:
        all_q = json.load(f)

    # Strictly use test split
    test_q = [q for q in all_q if q.get("split") == "test"]
    print(f"\nEvaluating retrieval across {len(test_q)} gold (Question, Reference Answer) test pairs...\n")

    corpus_answers = [q["answer"] for q in test_q]
    queries = [q["question"] for q in test_q]
    n_queries = len(queries)

    # 1. TF-IDF Model
    tfidf_vec = TFIDFVectorizer()
    tfidf_vec.fit(corpus_answers)
    answer_vecs = [tfidf_vec.transform(ans) for ans in corpus_answers]

    # 2. BM25 Model (Hand-implemented)
    bm25 = BM25()
    bm25.fit(corpus_answers)

    # 3. MiniLM Model
    embeddings = np.load(EMBEDDINGS_NPY)
    with open(EMBEDDINGS_IDS, "r", encoding="utf-8") as f:
        emb_ids = json.load(f)
    qid_to_idx = {qid: idx for idx, qid in enumerate(emb_ids)}

    # Encode test questions and answers with MiniLM
    from sentence_transformers import SentenceTransformer
    st_model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
    q_embs = st_model.encode(queries, normalize_embeddings=True, show_progress_bar=False)
    a_embs = st_model.encode(corpus_answers, normalize_embeddings=True, show_progress_bar=False)

    models = ["TF-IDF (Cosine)", "BM25 (Hand-made)", "MiniLM (Dense)"]
    metrics: Dict[str, Dict[str, float]] = {
        m: {"r1": 0.0, "r3": 0.0, "r5": 0.0, "mrr": 0.0} for m in models
    }

    for i in range(n_queries):
        true_idx = i

        # --- A. TF-IDF Ranking ---
        q_vec = tfidf_vec.transform(queries[i])
        tfidf_scores = [cosine_similarity(q_vec, a_vec) for a_vec in answer_vecs]
        tfidf_rank = np.argsort(tfidf_scores)[::-1]
        pos_tfidf = int(np.where(tfidf_rank == true_idx)[0][0]) + 1
        if pos_tfidf <= 1: metrics["TF-IDF (Cosine)"]["r1"] += 1
        if pos_tfidf <= 3: metrics["TF-IDF (Cosine)"]["r3"] += 1
        if pos_tfidf <= 5: metrics["TF-IDF (Cosine)"]["r5"] += 1
        metrics["TF-IDF (Cosine)"]["mrr"] += 1.0 / pos_tfidf

        # --- B. BM25 Ranking ---
        bm25_scores = [bm25.score(queries[i], doc_idx) for doc_idx in range(len(corpus_answers))]
        bm25_rank = np.argsort(bm25_scores)[::-1]
        pos_bm25 = int(np.where(bm25_rank == true_idx)[0][0]) + 1
        if pos_bm25 <= 1: metrics["BM25 (Hand-made)"]["r1"] += 1
        if pos_bm25 <= 3: metrics["BM25 (Hand-made)"]["r3"] += 1
        if pos_bm25 <= 5: metrics["BM25 (Hand-made)"]["r5"] += 1
        metrics["BM25 (Hand-made)"]["mrr"] += 1.0 / pos_bm25

        # --- C. MiniLM Ranking ---
        minilm_scores = np.dot(a_embs, q_embs[i])
        minilm_rank = np.argsort(minilm_scores)[::-1]
        pos_minilm = int(np.where(minilm_rank == true_idx)[0][0]) + 1
        if pos_minilm <= 1: metrics["MiniLM (Dense)"]["r1"] += 1
        if pos_minilm <= 3: metrics["MiniLM (Dense)"]["r3"] += 1
        if pos_minilm <= 5: metrics["MiniLM (Dense)"]["r5"] += 1
        metrics["MiniLM (Dense)"]["mrr"] += 1.0 / pos_minilm

    # Print Results Table
    print("-" * 80)
    print(f"{'Retrieval Model':<22} | {'Recall@1':<11} | {'Recall@3':<11} | {'Recall@5':<11} | {'MRR':<10}")
    print("-" * 80)
    for m in models:
        r1 = (metrics[m]["r1"] / n_queries) * 100
        r3 = (metrics[m]["r3"] / n_queries) * 100
        r5 = (metrics[m]["r5"] / n_queries) * 100
        mrr = metrics[m]["mrr"] / n_queries
        print(f"{m:<22} | {r1:<10.1f}% | {r3:<10.1f}% | {r5:<10.1f}% | {mrr:<10.3f}")
    print("-" * 80)
    print("\nRetrieval evaluation completed successfully.")


if __name__ == "__main__":
    evaluate_retrieval()
