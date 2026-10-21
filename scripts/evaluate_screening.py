"""Evaluate the resume screening model on the held-out test split.

Implements Phase 3 Step 4 and Section 2B.4 Item 4 of docs/spec/2B-dataset.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

import joblib
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, precision_score, recall_score

# Ensure root in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.app.config import settings

MODEL_FILE = settings.PROCESSED_DATA_DIR / "models" / "screening_model.joblib"
DATASET_FILE = settings.PROCESSED_DATA_DIR / "models" / "screening_dataset.joblib"


def main():
    print("=" * 75)
    print(f"{'PLUTO vProctor: Resume Screening Evaluation (Test Split)':^75}")
    print("=" * 75)

    if not MODEL_FILE.exists() or not DATASET_FILE.exists():
        print("Error: Models or dataset file missing. Run scripts/train_models.py first!")
        sys.exit(1)

    model = joblib.load(MODEL_FILE)
    dataset = joblib.load(DATASET_FILE)

    X_test = dataset["X_test"]
    y_test = dataset["y_test"]

    print(f"\nEvaluating on {len(X_test)} strictly held-out test resume-job pairs...\n")

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    cm = confusion_matrix(y_test, y_pred)

    print(f"Accuracy  : {acc * 100:.2f}%")
    print(f"Precision : {prec * 100:.2f}%")
    print(f"Recall    : {rec * 100:.2f}%")
    print(f"F1-Score  : {f1 * 100:.2f}%")

    print("\nConfusion Matrix:")
    print(f"{'':<15} | {'Predicted Reject':<18} | {'Predicted Pass':<16}")
    print("-" * 55)
    print(f"{'Actual Reject':<15} | {cm[0, 0]:<18} | {cm[0, 1]:<16}")
    print(f"{'Actual Pass':<15} | {cm[1, 0]:<18} | {cm[1, 1]:<16}")
    print("-" * 55)

    print("\nDetailed Classification Report:")
    print(classification_report(y_test, y_pred, target_names=["Reject", "Pass"]))

    print("Evaluation completed successfully.")


if __name__ == "__main__":
    main()
