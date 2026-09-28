"""
Classical-AIML layer for PLUTO vProctor (MDM AIML project, requirement 6).

This package holds the *named* machine-learning / search algorithms that back the
interview engine, kept apart from the interview services so they can be trained
offline (experiments/train_all.py), serialized to ``data/models/``, and loaded
lazily at runtime. Every runtime hook is feature-flagged in ``core/config.py`` and
falls back to the Elo/FSM/lexical/LLM baseline when its artifact is absent, so the
app behaves identically with or without trained models present.

Modules
-------
features        TF-IDF vectorizer + answer-vs-reference feature engineering (shared).
grader_ml       Supervised answer-correctness grader: NB/LogReg/SVM/kNN/Tree +
                Linear/Ridge/Lasso/ElasticNet/Polynomial regression + Stacking/
                Bagging/AdaBoost ensembles. Blends into eval_tier1.
topics          Unsupervised structure: KMeans/Agglomerative/DBSCAN clustering,
                PCA/LDA reduction, kNN résumé→question ranking, Apriori skill rules.
selection_search  A*/Greedy/BFS/DLS/IDS/Bidirectional over a per-domain difficulty graph.
selection_csp   CSP (backtracking + forward-checking) pool assembly + GA/local search.
difficulty_reg  Regression difficulty calibration + probability ability bands.

Design invariants inherited from the interview engine:
  * ML touches only the CONTENT score S; delivery signals stay descriptive.
  * The answer key never leaves the server — models emit scores, never references.
  * CPU-only (scikit-learn); no GPU/DL, honoring the 6 GB VRAM budget.
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# core/aiml/ -> project root is two parents up (core/aiml/__init__.py).
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
# Raw imported Q&A dataset (train/val/test .jsonl) used to TRAIN the grader.
DATASET_DIR = PROJECT_ROOT.parent / "archive" / "data"


def models_dir() -> Path:
    """Resolve MODELS_DIR from config (default data/models), relative to the root."""
    try:
        from core import config
        raw = getattr(config, "MODELS_DIR", "data/models")
    except Exception:
        raw = "data/models"
    p = Path(raw)
    return p if p.is_absolute() else (PROJECT_ROOT / p)


def artifact_path(name: str) -> Path:
    """Path to a serialized model artifact under MODELS_DIR (e.g. 'grader.joblib')."""
    return models_dir() / name


def flag(name: str, default: bool = True) -> bool:
    """Read an AIML_* feature flag from core/config.py (default True)."""
    try:
        from core import config
        return bool(getattr(config, name, default))
    except Exception:
        return default
