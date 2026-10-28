"""Train and evaluate the answer-relevance classifier with hard negatives.

Implements Section 2B.4 Item 3 of docs/spec/2B-dataset.md:
Features: MiniLM cosine, TF-IDF cosine, keyword recall, length ratio, BM25.
Models: Logistic Regression vs Gradient Boosting.
Reports: Accuracy, Precision, Recall, F1, ROC-AUC on test split.
Saves: backend/app/data/processed/models/answer_relevance_model.joblib
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

# Ensure root in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.app.algorithms.bm25 import BM25
from backend.app.algorithms.similarity import TFIDFVectorizer, cosine_similarity, tokenize
from backend.app.config import settings

QUESTIONS_JSON = settings.PROCESSED_DATA_DIR / "questions.json"
MODELS_DIR = settings.PROCESSED_DATA_DIR / "models"
MODEL_OUT = MODELS_DIR / "answer_relevance_model.joblib"


def extract_pair_features(
    q_text: str,
    a_text: str,
    exp_keywords: List[str],
    tfidf_vec: TFIDFVectorizer,
    bm25: BM25,
    q_emb: np.ndarray,
    a_emb: np.ndarray,
) -> List[float]:
    """Compute 5 dense multimodal features between question/expected and candidate answer."""
    # 1. MiniLM embedding cosine
    emb_sim = float(np.dot(q_emb, a_emb) / (np.linalg.norm(q_emb) * np.linalg.norm(a_emb) + 1e-9))

    # 2. TF-IDF cosine
    qv = tfidf_vec.transform(q_text)
    av = tfidf_vec.transform(a_text)
    tfidf_sim = float(cosine_similarity(qv, av))

    # 3. Keyword recall (fraction of expected keywords found in answer)
    a_tokens = set(tokenize(a_text))
    if exp_keywords:
        kw_hits = sum(1 for kw in exp_keywords if any(t in a_tokens for t in tokenize(kw)))
        kw_recall = kw_hits / float(len(exp_keywords))
    else:
        kw_recall = 0.5

    # 4. Answer length ratio (min/max of words)
    q_len = max(1, len(q_text.split()))
    a_len = max(1, len(a_text.split()))
    len_ratio = min(q_len, a_len) / float(max(q_len, a_len))

    # 5. BM25 score
    bm25_val = float(bm25.score(q_text, 0))  # relative score

    return [emb_sim, tfidf_sim, kw_recall, len_ratio, bm25_val]


def build_dataset_split(
    q_list: List[Dict[str, Any]],
    tfidf_vec: TFIDFVectorizer,
    bm25: BM25,
    st_model,
) -> Tuple[np.ndarray, np.ndarray]:
    """Create positive and hard-negative pairs from a question split."""
    random.seed(42)
    # Pre-encode all queries and answers
    q_texts = [q["question"] for q in q_list]
    a_texts = [q["answer"] for q in q_list]

    q_embs = st_model.encode(q_texts, normalize_embeddings=True, show_progress_bar=False)
    a_embs = st_model.encode(a_texts, normalize_embeddings=True, show_progress_bar=False)

    # Group questions by cluster or domain for hard-negative sampling
    domain_groups = {}
    for i, q in enumerate(q_list):
        dom = q.get("domain", "General")
        domain_groups.setdefault(dom, []).append(i)

    X = []
    y = []

    for i, q in enumerate(q_list):
        # Positive pair (label = 1)
        feat_pos = extract_pair_features(
            q["question"], q["answer"], q.get("expected_keywords", []),
            tfidf_vec, bm25, q_embs[i], a_embs[i]
        )
        X.append(feat_pos)
        y.append(1)

        # Hard negative pair from same domain (label = 0)
        dom = q.get("domain", "General")
        group = domain_groups.get(dom, [])
        candidates = [idx for idx in group if idx != i]
        neg_idx = random.choice(candidates) if candidates else random.choice([idx for idx in range(len(q_list)) if idx != i])

        feat_neg = extract_pair_features(
            q["question"], q_list[neg_idx]["answer"], q.get("expected_keywords", []),
            tfidf_vec, bm25, q_embs[i], a_embs[neg_idx]
        )
        X.append(feat_neg)
        y.append(0)

    return np.array(X), np.array(y)


def main():
    print("=" * 80)
    print(f"{'PLUTO vProctor: Answer Relevance Classifier Evaluation':^80}")
    print("=" * 80)

    with open(QUESTIONS_JSON, "r", encoding="utf-8") as f:
        all_q = json.load(f)

    train_q = [q for q in all_q if q.get("split") == "train"]
    val_q = [q for q in all_q if q.get("split") == "val"]
    test_q = [q for q in all_q if q.get("split") == "test"]

    print(f"Data splits: Train={len(train_q)}, Val={len(val_q)}, Test={len(test_q)}")

    # Fit TF-IDF and BM25 on TRAIN split only
    train_corpus = [q["answer"] for q in train_q]
    tfidf_vec = TFIDFVectorizer()
    tfidf_vec.fit(train_corpus)

    bm25 = BM25()
    bm25.fit(train_corpus)

    from sentence_transformers import SentenceTransformer
    st_model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")

    print("\nExtracting multimodal features on train split (with hard negatives)...")
    X_train, y_train = build_dataset_split(train_q, tfidf_vec, bm25, st_model)
    print(f"Generated train feature matrix: {X_train.shape}")

    print("Extracting multimodal features on val split...")
    X_val, y_val = build_dataset_split(val_q, tfidf_vec, bm25, st_model)

    print("Extracting multimodal features on strictly held-out test split...")
    X_test, y_test = build_dataset_split(test_q, tfidf_vec, bm25, st_model)

    # 1. Fit Logistic Regression
    lr = LogisticRegression(C=2.0, max_iter=300, random_state=42)
    lr.fit(X_train, y_train)

    # 2. Fit Gradient Boosting baseline
    gb = GradientBoostingClassifier(n_estimators=100, learning_rate=0.1, max_depth=3, random_state=42)
    gb.fit(X_train, y_train)

    # Evaluate on Test split
    models = [("Logistic Regression", lr), ("Gradient Boosting", gb)]

    print("\n" + "-" * 80)
    header = f"{'Model':<24} | {'Accuracy':<10} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10} | {'ROC-AUC':<10}"
    print(header)
    print("-" * 80)

    for name, m in models:
        preds = m.predict(X_test)
        probs = m.predict_proba(X_test)[:, 1]

        acc = accuracy_score(y_test, preds) * 100
        prec = precision_score(y_test, preds) * 100
        rec = recall_score(y_test, preds) * 100
        f1 = f1_score(y_test, preds) * 100
        auc = roc_auc_score(y_test, probs)

        print(f"{name:<24} | {acc:<9.1f}% | {prec:<9.1f}% | {rec:<9.1f}% | {f1:<9.1f}% | {auc:<10.3f}")

    print("-" * 80)

    # Save best model to disk
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(lr, MODEL_OUT)
    print(f"\nSaved answer relevance model to {MODEL_OUT}")

    # Print Confusion Matrix for best model
    from sklearn.metrics import confusion_matrix
    cm = confusion_matrix(y_test, lr.predict(X_test))
    print("\nTest Confusion Matrix (Logistic Regression):")
    print(f"  True Negatives (Correct Hard-Neg Rejections): {cm[0, 0]}")
    print(f"  False Positives (Irrelevant accepted):        {cm[0, 1]}")
    print(f"  False Negatives (True answer missed):         {cm[1, 0]}")
    print(f"  True Positives (Correctly identified answer): {cm[1, 1]}")

    print("\nAnswer relevance evaluation completed successfully.")


if __name__ == "__main__":
    main()
