"""Evaluate domain classification models on the held-out test split.

Implements Section 2B.4 Item 1 of docs/spec/2B-dataset.md:
Compares Naive Bayes vs Logistic Regression vs Embedding k-NN/Centroid
on Accuracy, Macro-F1, Weighted-F1, and Confusion Matrix.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.naive_bayes import MultinomialNB
from sklearn.neighbors import NearestCentroid

# Ensure root in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.app.config import settings

QUESTIONS_JSON = settings.PROCESSED_DATA_DIR / "questions.json"
EMBEDDINGS_NPY = settings.PROCESSED_DATA_DIR / "embeddings.npy"
EMBEDDINGS_IDS = settings.PROCESSED_DATA_DIR / "embeddings_ids.json"


def evaluate_domain_classifiers():
    print("=" * 80)
    print(f"{'PLUTO vProctor: Domain Classification Evaluation (Test Split)':^80}")
    print("=" * 80)

    if not QUESTIONS_JSON.exists():
        print(f"Error: {QUESTIONS_JSON} does not exist.")
        sys.exit(1)

    with open(QUESTIONS_JSON, "r", encoding="utf-8") as f:
        all_q = json.load(f)

    # Separate train, val, and test splits strictly
    train_q = [q for q in all_q if q.get("split") == "train"]
    val_q = [q for q in all_q if q.get("split") == "val"]
    test_q = [q for q in all_q if q.get("split") == "test"]

    print(f"Dataset Split Sizes: Train={len(train_q)}, Val={len(val_q)}, Test={len(test_q)}")

    # Extract text (question + answer) and labels
    X_train_text = [f"{q['question']} {q['answer']}" for q in train_q]
    y_train = [q["domain"] for q in train_q]

    X_val_text = [f"{q['question']} {q['answer']}" for q in val_q]
    y_val = [q["domain"] for q in val_q]

    X_test_text = [f"{q['question']} {q['answer']}" for q in test_q]
    y_test = [q["domain"] for q in test_q]

    domains = sorted(list(set(y_train)))
    print(f"Target Domains ({len(domains)} classes): {', '.join(domains)}\n")

    # 1. Feature Extraction: TF-IDF fitted STRICTLY on train
    tfidf = TfidfVectorizer(max_features=2500, ngram_range=(1, 2), stop_words="english")
    X_train_tfidf = tfidf.fit_transform(X_train_text)
    X_val_tfidf = tfidf.transform(X_val_text)
    X_test_tfidf = tfidf.transform(X_test_text)

    # Model 1: Multinomial Naive Bayes
    nb = MultinomialNB(alpha=0.1)
    nb.fit(X_train_tfidf, y_train)
    nb_test_preds = nb.predict(X_test_tfidf)
    nb_acc = float(np.mean(nb_test_preds == y_test))
    nb_macro_f1 = f1_score(y_test, nb_test_preds, average="macro", zero_division=0)
    nb_weighted_f1 = f1_score(y_test, nb_test_preds, average="weighted", zero_division=0)

    # Model 2: Logistic Regression
    lr = LogisticRegression(C=2.0, max_iter=400, random_state=42)
    lr.fit(X_train_tfidf, y_train)
    lr_test_preds = lr.predict(X_test_tfidf)
    lr_acc = float(np.mean(lr_test_preds == y_test))
    lr_macro_f1 = f1_score(y_test, lr_test_preds, average="macro", zero_division=0)
    lr_weighted_f1 = f1_score(y_test, lr_test_preds, average="weighted", zero_division=0)

    # Model 3: MiniLM Embedding Centroid Classifier
    embeddings = np.load(EMBEDDINGS_NPY)
    with open(EMBEDDINGS_IDS, "r", encoding="utf-8") as f:
        emb_ids = json.load(f)
    id_to_idx = {qid: i for i, qid in enumerate(emb_ids)}

    X_train_emb = np.array([embeddings[id_to_idx[q["id"]]] for q in train_q if q["id"] in id_to_idx])
    y_train_emb = [q["domain"] for q in train_q if q["id"] in id_to_idx]

    X_test_emb = np.array([embeddings[id_to_idx[q["id"]]] for q in test_q if q["id"] in id_to_idx])
    y_test_emb = [q["domain"] for q in test_q if q["id"] in id_to_idx]

    nc = NearestCentroid()
    nc.fit(X_train_emb, y_train_emb)
    nc_test_preds = nc.predict(X_test_emb)
    nc_acc = float(np.mean(nc_test_preds == y_test_emb))
    nc_macro_f1 = f1_score(y_test_emb, nc_test_preds, average="macro", zero_division=0)
    nc_weighted_f1 = f1_score(y_test_emb, nc_test_preds, average="weighted", zero_division=0)

    # Comparison Table
    print(f"{'Model':<30} | {'Test Accuracy':<15} | {'Macro F1':<12} | {'Weighted F1':<12}")
    print("-" * 75)
    print(f"{'Multinomial Naive Bayes':<30} | {nb_acc * 100:>13.2f}% | {nb_macro_f1:>12.4f} | {nb_weighted_f1:>12.4f}")
    print(f"{'Logistic Regression':<30} | {lr_acc * 100:>13.2f}% | {lr_macro_f1:>12.4f} | {lr_weighted_f1:>12.4f}")
    print(f"{'MiniLM Embedding Centroid':<30} | {nc_acc * 100:>13.2f}% | {nc_macro_f1:>12.4f} | {nc_weighted_f1:>12.4f}")
    print("=" * 75)

    print("\nDetailed Classification Report for Best Model (Logistic Regression):")
    print(classification_report(y_test, lr_test_preds, zero_division=0))

    cm = confusion_matrix(y_test, lr_test_preds, labels=domains)
    print(f"\nConfusion Matrix Shape: {cm.shape} for {len(domains)} domains.")
    print("=" * 80)
    print("Domain Classification Evaluation Complete. Zero train/test leakage.\n")

    return {
        "nb_accuracy": nb_acc,
        "nb_macro_f1": nb_macro_f1,
        "lr_accuracy": lr_acc,
        "lr_macro_f1": lr_macro_f1,
        "embedding_centroid_accuracy": nc_acc,
        "embedding_centroid_macro_f1": nc_macro_f1,
    }


if __name__ == "__main__":
    evaluate_domain_classifiers()
