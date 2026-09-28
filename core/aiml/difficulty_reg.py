"""
Difficulty regression + probability ability bands for PLUTO vProctor
(MDM AIML, requirement 4 + 6).

Two named-algorithm pieces that feed the END REPORT as DESCRIPTIVE calibration
information (never a verdict, never a score):

  Regression (Linear/Ridge/Lasso/ElasticNet/Polynomial/RandomForest)
      learns irt.b (authored difficulty) from a question's content features, so
      the report can note when an item's *authored* tier looks out of step with
      its content ("difficulty check"). Compared by R^2 / MAE; best is shipped.

  Probability distribution (1-PL / Rasch Fisher information)
      turns the Elo ability point-estimate into an 80% CONFIDENCE BAND. The
      logistic item model P(theta) = 1/(1+10^((b-theta)/400)) has Fisher info
      I(theta) = (ln10/400)^2 * sum P(1-P); SE = 1/sqrt(I); band = theta +/- z*SE.

Feature-flagged (AIML_CALIBRATION_ENABLED). The ability band is pure math (no
artifact); the difficulty check needs difficulty.joblib and is simply omitted
when the model is absent. report.py adds the block only when the flag is on, so
the report is unchanged when the layer is off.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from core.aiml import artifact_path, flag

RANDOM_SEED = 13
DIFFICULTY_ARTIFACT = "difficulty.joblib"
LN10_OVER_400 = math.log(10) / 400.0
Z_80 = 1.2816                      # 80% two-sided normal quantile

STRUCT_NAMES = ["n_words", "mean_word_len", "n_tags", "n_keywords",
                "n_ideal_points", "n_chars"]


def _b(q: dict) -> float:
    return float((q.get("irt") or {}).get("b", 1300))


def _struct(q: dict) -> List[float]:
    text = q.get("text", "") or ""
    words = text.split()
    nw = len(words)
    return [
        float(nw),
        (sum(len(w) for w in words) / nw) if nw else 0.0,
        float(len(q.get("tags", []) or [])),
        float(len(q.get("keywords", []) or [])),
        float(len(q.get("ideal_answer_points", []) or [])),
        float(len(text)),
    ]


def _features(q: dict, categories: List[str]) -> np.ndarray:
    vec = _struct(q) + [1.0 if q.get("category", "?") == c else 0.0
                        for c in categories]
    return np.array(vec, dtype=float)

# ---- probability ability band (1-PL Fisher information) -------------------
def _expected(theta: float, b: float) -> float:
    """1-PL / Rasch success probability of ability theta on an item of diff b."""
    return 1.0 / (1.0 + 10 ** ((b - theta) / 400.0))


def ability_confidence(ability: float, answers) -> Dict:
    """Probability-distribution confidence band around the Elo ability estimate.

    Uses the 1-PL item-response model's Fisher information over the answered
    items: more items (and items near the ability) tighten the band. Purely
    DESCRIPTIVE — it quantifies estimate uncertainty, not performance."""
    bs = [float(getattr(a, "b_question", 1300) or 1300) for a in (answers or [])]
    n = len(bs)
    if n == 0:
        return {"ability_elo": round(ability, 1), "n_items": 0,
                "note": "No answers yet — ability band undefined."}
    info = (LN10_OVER_400 ** 2) * sum(
        (p := _expected(ability, b)) * (1 - p) for b in bs)
    if info <= 0:
        se = float("inf")
    else:
        se = 1.0 / math.sqrt(info)
    lo, hi = ability - Z_80 * se, ability + Z_80 * se
    return {
        "ability_elo": round(ability, 1),
        "standard_error_elo": round(se, 1) if math.isfinite(se) else None,
        "band_80pct_elo": [round(lo, 1), round(hi, 1)] if math.isfinite(se) else None,
        "n_items": n,
        "note": ("Wider band = fewer/less-informative items; this is estimate "
                 "uncertainty, not a performance judgment."),
    }


# ---- difficulty regression (calibration check) ----------------------------
@dataclass
class DifficultyArtifact:
    categories: List[str]
    model: object                  # best regressor: features -> irt.b
    feature_names: List[str]
    metrics: Dict
    chosen: str


def load_questions() -> List[dict]:
    from core.interview.question_bank import get_question_bank
    return get_question_bank().all_questions()


def _regressors() -> Dict[str, object]:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import ElasticNet, Lasso, LinearRegression, Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import PolynomialFeatures, StandardScaler
    return {
        "Linear": make_pipeline(StandardScaler(), LinearRegression()),
        "Ridge": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
        "Lasso": make_pipeline(StandardScaler(), Lasso(alpha=0.01, max_iter=5000)),
        "ElasticNet": make_pipeline(StandardScaler(),
                                    ElasticNet(alpha=0.01, l1_ratio=0.5, max_iter=5000)),
        "Polynomial(deg2)": make_pipeline(
            StandardScaler(), PolynomialFeatures(2, include_bias=False), Ridge(alpha=1.0)),
        "RandomForest": RandomForestRegressor(n_estimators=120, random_state=RANDOM_SEED),
    }

def train(verbose: bool = True) -> Tuple["DifficultyArtifact", Dict]:
    """Fit + compare regressors that predict irt.b from question features; ship
    the best by R^2 (refit on all rows). Returns (artifact, metrics)."""
    from sklearn.metrics import mean_absolute_error, r2_score
    from sklearn.model_selection import train_test_split

    qs = load_questions()
    categories = sorted({q.get("category", "?") for q in qs})
    X = np.vstack([_features(q, categories) for q in qs])
    y = np.array([_b(q) for q in qs], dtype=float)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2,
                                          random_state=RANDOM_SEED)
    metrics: Dict = {"n_questions": len(qs), "n_features": X.shape[1],
                     "regressors": {}}
    best, best_name, best_r2 = None, None, -1e9
    for name, mdl in _regressors().items():
        mdl.fit(Xtr, ytr)
        pred = mdl.predict(Xte)
        r2 = r2_score(yte, pred)
        metrics["regressors"][name] = {"r2": round(float(r2), 4),
                                       "mae": round(float(mean_absolute_error(yte, pred)), 2)}
        if r2 > best_r2:
            best, best_name, best_r2 = mdl, name, r2
    best.fit(X, y)                                    # refit on all for deployment
    metrics["chosen"] = best_name
    feat_names = STRUCT_NAMES + [f"cat={c}" for c in categories]
    art = DifficultyArtifact(categories, best, feat_names, metrics, best_name)
    if verbose:
        print(f"\n[difficulty] {len(qs)} questions, {X.shape[1]} features "
              f"-> predict irt.b")
        for name, s in metrics["regressors"].items():
            print(f"    {name:<18} R^2 {s['r2']:>7.3f}   MAE {s['mae']:>7.2f}")
        print(f"    chosen -> {best_name}")
    return art, metrics


def save(art: "DifficultyArtifact", path: Optional[Path] = None) -> Path:
    import joblib
    p = Path(path) if path else artifact_path(DIFFICULTY_ARTIFACT)
    p.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(art, p)
    return p


def train_and_save(path: Optional[Path] = None, verbose: bool = True):
    art, metrics = train(verbose=verbose)
    p = save(art, path)
    if verbose:
        print(f"[difficulty] saved -> {p}")
    return p, metrics


class DifficultyModel:
    """Runtime wrapper: predict a question's irt.b from its content features."""

    def __init__(self, art: DifficultyArtifact):
        self.art = art

    @classmethod
    def load(cls, path: Optional[Path] = None) -> Optional["DifficultyModel"]:
        import joblib
        p = Path(path) if path else artifact_path(DIFFICULTY_ARTIFACT)
        if not p.exists():
            return None
        try:
            return cls(joblib.load(p))
        except Exception:
            return None

    def predict_b(self, question: dict) -> float:
        x = _features(question, self.art.categories).reshape(1, -1)
        return float(self.art.model.predict(x)[0])

def calibration(bank, answers, model: Optional["DifficultyModel"]) -> Optional[Dict]:
    """Compare each answered item's AUTHORED difficulty (irt.b) with the value
    the regression predicts from its content. Purely descriptive: it flags where
    the authored tier may not match the content, never the candidate."""
    if model is None or not answers:
        return None
    rows = []
    for a in answers:
        q = bank.get(getattr(a, "question_id", None)) or {}
        if not q:
            continue
        authored = _b(q)
        pred = model.predict_b(q)
        rows.append({"question_id": q.get("id"), "category": q.get("category"),
                     "authored_b": round(authored, 1), "predicted_b": round(pred, 1),
                     "delta": round(pred - authored, 1)})
    if not rows:
        return None
    mad = round(sum(abs(r["delta"]) for r in rows) / len(rows), 1)
    outliers = sorted(rows, key=lambda r: abs(r["delta"]), reverse=True)[:3]
    return {
        "mean_abs_deviation_elo": mad,
        "n_items": len(rows),
        "largest_authoring_gaps": outliers,
        "note": ("Difference between a question's authored tier and its content-"
                 "predicted difficulty; a question-authoring signal, not a score."),
    }


_SINGLETON: Optional[DifficultyModel] = None
_LOAD_TRIED = False


def get_difficulty_model() -> Optional[DifficultyModel]:
    """Lazy singleton. None when AIML_CALIBRATION_ENABLED is off or no artifact."""
    global _SINGLETON, _LOAD_TRIED
    if not flag("AIML_CALIBRATION_ENABLED", True):
        return None
    if _SINGLETON is None and not _LOAD_TRIED:
        _LOAD_TRIED = True
        _SINGLETON = DifficultyModel.load()
    return _SINGLETON


if __name__ == "__main__":
    from core.aiml.difficulty_reg import train_and_save as _train_and_save
    _train_and_save()



