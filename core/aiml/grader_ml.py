"""
Supervised answer-correctness grader for PLUTO vProctor (MDM AIML, requirement 3+6).

The named-algorithm engine behind the CONTENT score S. It learns "how well does
this candidate answer match the correct answer's text" from the imported Q&A
dataset (../archive/data/*.jsonl, 1806 pairs) and, at runtime, scores a live
answer against the question's ideal_answer_points+keywords — the same geometry.

Algorithms compared + shipped (all CPU-only scikit-learn):
  classifiers (correct/partial/incorrect band):  Naive Bayes, Logistic Regression,
      Linear SVM, kNN, Decision Tree, RandomForest (Bagging), AdaBoost (Boosting)
  regressors (continuous S in [0,1]):            Linear, Ridge, Lasso, ElasticNet,
      Polynomial, RandomForest, kNN
  runtime ensemble:                              Stacking (Ridge+RF+kNN -> Ridge)

Training labels come from NEGATIVE SAMPLING over the gold pairs (documented in
build_frame): the gold answer is a CORRECT example against its own distilled
reference; a truncated/word-dropout copy is PARTIAL; a different question's answer
is INCORRECT. This mirrors exactly what the runtime grader must judge.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from core.aiml import DATASET_DIR, artifact_path, flag
from core.aiml.features import FEATURE_NAMES, FeatureExtractor, _content, _tokens

RANDOM_SEED = 13
GRADER_ARTIFACT = "grader.joblib"

LABEL_INCORRECT, LABEL_PARTIAL, LABEL_CORRECT = 0, 1, 2
BAND_NAMES = {0: "incorrect", 1: "partial", 2: "correct"}


def load_pairs() -> List[Tuple[str, str]]:
    """Read every {"question","answer"} row from the raw train/val/test jsonl."""
    pairs: List[Tuple[str, str]] = []
    for name in ("train.jsonl", "val.jsonl", "test.jsonl"):
        fp = DATASET_DIR / name
        if not fp.exists():
            continue
        for line in fp.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            q = (obj.get("question") or "").strip()
            a = (obj.get("answer") or "").strip()
            if q and a:
                pairs.append((q, a))
    return pairs


def _distill(answer: str, cap: int = 40) -> str:
    """Approximate a question's ideal_answer_points/keywords from a gold answer:
    its ordered, de-duplicated content words. Using this (not the raw answer) as
    the training reference makes the (candidate vs reference) geometry match the
    runtime case, where the reference is the distilled ideal points + keywords."""
    content = _content(answer)
    seen, out = set(), []
    for t in _tokens(answer):
        if t in content and t not in seen:
            seen.add(t)
            out.append(t)
    return " ".join(out[:cap]) or " ".join(_tokens(answer)[:cap])


def _truncate(text: str, keep: float) -> str:
    w = text.split()
    n = max(1, int(len(w) * keep))
    return " ".join(w[:n])


def _dropout(text: str, keep: float, rng: random.Random) -> str:
    w = text.split()
    if len(w) <= 3:
        return text
    kept = [t for t in w if rng.random() < keep]
    return " ".join(kept) if kept else _truncate(text, 0.4)


def build_frame(pairs: List[Tuple[str, str]], seed: int = RANDOM_SEED):
    """Negative-sampling training frame -> rows of (candidate, reference, band, S).

    Per gold (q, a) with reference = distill(a):
      CORRECT (S=1.0)   candidate = the gold answer a
      PARTIAL (S~0.5)   candidate = a truncated OR word-dropout copy of a
      INCORRECT (S=0.0) candidate = a *different* question's answer
      + occasional empty/stub candidate (mirrors the eval_tier1 non-answer guard)
    """
    rng = random.Random(seed)
    answers = [a for _, a in pairs]
    n = len(pairs)
    rows: List[Tuple[str, str, int, float]] = []
    for i, (_q, a) in enumerate(pairs):
        ref = _distill(a)
        rows.append((a, ref, LABEL_CORRECT, 1.0))
        if rng.random() < 0.5:
            cand = _truncate(a, rng.uniform(0.35, 0.6))
        else:
            cand = _dropout(a, rng.uniform(0.45, 0.65), rng)
        rows.append((cand, ref, LABEL_PARTIAL, round(rng.uniform(0.45, 0.6), 3)))
        j = rng.randrange(n)
        if j == i and n > 1:
            j = (j + 1) % n
        rows.append((answers[j], ref, LABEL_INCORRECT, 0.0))
        if rng.random() < 0.12:
            stub = " ".join(a.split()[: rng.randint(0, 3)])
            rows.append((stub, ref, LABEL_INCORRECT, 0.0))
    rng.shuffle(rows)
    return rows


def _xy(extractor: FeatureExtractor, rows):
    X = extractor.transform([(c, r) for c, r, _, _ in rows])
    y_cls = np.array([lab for _, _, lab, _ in rows])
    y_reg = np.array([tgt for _, _, _, tgt in rows], dtype=float)
    return X, y_cls, y_reg


def _classifiers() -> Dict[str, object]:
    from sklearn.ensemble import AdaBoostClassifier, RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.naive_bayes import GaussianNB
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.svm import LinearSVC
    from sklearn.tree import DecisionTreeClassifier
    return {
        "NaiveBayes": GaussianNB(),
        "LogisticRegression": LogisticRegression(max_iter=1000),
        "LinearSVM": LinearSVC(),
        "kNN": KNeighborsClassifier(n_neighbors=15),
        "DecisionTree": DecisionTreeClassifier(max_depth=6, random_state=RANDOM_SEED),
        "RandomForest(Bagging)": RandomForestClassifier(
            n_estimators=120, random_state=RANDOM_SEED),
        "AdaBoost(Boosting)": AdaBoostClassifier(
            n_estimators=120, random_state=RANDOM_SEED),
    }


def _regressors() -> Dict[str, object]:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import ElasticNet, Lasso, LinearRegression, Ridge
    from sklearn.neighbors import KNeighborsRegressor
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import PolynomialFeatures
    return {
        "Linear": LinearRegression(),
        "Ridge": Ridge(alpha=1.0),
        "Lasso": Lasso(alpha=0.001),
        "ElasticNet": ElasticNet(alpha=0.001, l1_ratio=0.5),
        "Polynomial(deg2)": make_pipeline(
            PolynomialFeatures(2, include_bias=False), Ridge(alpha=1.0)),
        "RandomForest(Bagging)": RandomForestRegressor(
            n_estimators=120, random_state=RANDOM_SEED),
        "kNN": KNeighborsRegressor(n_neighbors=15),
    }


def _stacking_regressor():
    """The runtime S-emitter: a Stacking ensemble (Ridge + RF + kNN -> Ridge),
    passthrough=True so the meta-learner also sees the raw lexical features."""
    from sklearn.ensemble import RandomForestRegressor, StackingRegressor
    from sklearn.linear_model import Ridge
    from sklearn.neighbors import KNeighborsRegressor
    return StackingRegressor(
        estimators=[
            ("ridge", Ridge(alpha=1.0)),
            ("rf", RandomForestRegressor(n_estimators=120, random_state=RANDOM_SEED)),
            ("knn", KNeighborsRegressor(n_neighbors=15)),
        ],
        final_estimator=Ridge(alpha=0.5),
        passthrough=True,
    )


@dataclass
class GraderArtifact:
    """Everything the runtime grader needs, serialized as one joblib file."""
    extractor: FeatureExtractor
    regressor: object          # Stacking ensemble -> continuous S in [0,1]
    classifier: object         # 3-band correct/partial/incorrect (diagnostics)
    feature_names: List[str]
    metrics: Dict
    band_names: Dict


def train(verbose: bool = True) -> Tuple["GraderArtifact", Dict]:
    """Fit + compare every algorithm, pick the best classifier by macro-F1, and
    ship the Stacking regressor as the runtime S-emitter. Returns (artifact, metrics)."""
    from sklearn.metrics import (accuracy_score, f1_score, mean_absolute_error,
                                 r2_score)
    from sklearn.model_selection import train_test_split

    pairs = load_pairs()
    if len(pairs) < 20:
        raise RuntimeError(f"grader training needs the raw dataset at {DATASET_DIR}")
    extractor = FeatureExtractor().fit([a for _, a in pairs] + [q for q, _ in pairs])
    rows = build_frame(pairs)
    X, y_cls, y_reg = _xy(extractor, rows)
    Xtr, Xte, ycl_tr, ycl_te, yr_tr, yr_te = train_test_split(
        X, y_cls, y_reg, test_size=0.2, random_state=RANDOM_SEED, stratify=y_cls)

    metrics: Dict = {"n_pairs": len(pairs), "n_rows": len(rows),
                     "classifiers": {}, "regressors": {}}
    best_clf = best_clf_name = None
    best_f1 = -1.0
    for name, mdl in _classifiers().items():
        mdl.fit(Xtr, ycl_tr)
        pred = mdl.predict(Xte)
        f1 = f1_score(ycl_te, pred, average="macro", zero_division=0)
        metrics["classifiers"][name] = {
            "accuracy": round(accuracy_score(ycl_te, pred), 4),
            "macro_f1": round(f1, 4)}
        if f1 > best_f1:
            best_clf, best_clf_name, best_f1 = mdl, name, f1

    for name, mdl in _regressors().items():
        mdl.fit(Xtr, yr_tr)
        pred = np.clip(mdl.predict(Xte), 0.0, 1.0)
        metrics["regressors"][name] = {
            "r2": round(r2_score(yr_te, pred), 4),
            "mae": round(mean_absolute_error(yr_te, pred), 4)}

    stack = _stacking_regressor()
    stack.fit(Xtr, yr_tr)
    spred = np.clip(stack.predict(Xte), 0.0, 1.0)
    metrics["regressors"]["Stacking(runtime)"] = {
        "r2": round(r2_score(yr_te, spred), 4),
        "mae": round(mean_absolute_error(yr_te, spred), 4)}

    # Refit the shipped models on ALL rows for deployment.
    stack.fit(X, y_reg)
    best_clf.fit(X, y_cls)
    metrics["chosen"] = {"regressor": "Stacking(runtime)", "classifier": best_clf_name}
    art = GraderArtifact(extractor, stack, best_clf, list(FEATURE_NAMES),
                         metrics, dict(BAND_NAMES))
    if verbose:
        _print_metrics(metrics)
    return art, metrics


def _print_metrics(m: Dict) -> None:
    print(f"\n[grader] {m['n_pairs']} gold pairs -> {m['n_rows']} labeled rows")
    print("  classifiers (band: correct/partial/incorrect)      acc   macroF1")
    for name, s in m["classifiers"].items():
        print(f"    {name:<28} {s['accuracy']:>6.3f}  {s['macro_f1']:>6.3f}")
    print("  regressors (continuous S in [0,1])                  R^2     MAE")
    for name, s in m["regressors"].items():
        print(f"    {name:<28} {s['r2']:>7.3f} {s['mae']:>7.3f}")
    print(f"  chosen -> classifier={m['chosen']['classifier']} "
          f"regressor={m['chosen']['regressor']}")


def save(art: "GraderArtifact", path: Optional[Path] = None) -> Path:
    import joblib
    p = Path(path) if path else artifact_path(GRADER_ARTIFACT)
    p.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(art, p)
    return p


def train_and_save(path: Optional[Path] = None, verbose: bool = True):
    art, metrics = train(verbose=verbose)
    p = save(art, path)
    if verbose:
        print(f"[grader] saved -> {p}")
    return p, metrics

class MLGrader:
    """Runtime wrapper: score a live answer against a question's ideal points."""

    def __init__(self, art: GraderArtifact):
        self.art = art

    @classmethod
    def load(cls, path: Optional[Path] = None) -> Optional["MLGrader"]:
        import joblib
        p = Path(path) if path else artifact_path(GRADER_ARTIFACT)
        if not p.exists():
            return None
        try:
            return cls(joblib.load(p))
        except Exception:
            return None

    def _reference(self, question: dict) -> str:
        """The correct-answer text the model scores against: ideal points +
        keywords (never leaves the server). Falls back to the question text."""
        pts = question.get("ideal_answer_points") or []
        kws = question.get("keywords") or []
        ref = " ".join([str(x) for x in pts] + [str(x) for x in kws]).strip()
        return ref or (question.get("text") or "")

    def _feats(self, question: dict, answer_text: str):
        ref = self._reference(question)
        return self.art.extractor.pair_features(answer_text or "", ref).reshape(1, -1)

    def score(self, question: dict, answer_text: str) -> float:
        """Continuous CONTENT score S in [0,1] from the Stacking ensemble."""
        s = float(self.art.regressor.predict(self._feats(question, answer_text))[0])
        return max(0.0, min(1.0, s))

    def band(self, question: dict, answer_text: str) -> str:
        """Diagnostic label: 'correct' / 'partial' / 'incorrect'."""
        lab = int(self.art.classifier.predict(self._feats(question, answer_text))[0])
        return self.art.band_names.get(lab, "partial")


_SINGLETON: Optional[MLGrader] = None
_LOAD_TRIED = False


def get_ml_grader() -> Optional[MLGrader]:
    """Lazy singleton. Returns None when the flag is off or no artifact exists,
    so callers transparently fall back to the lexical baseline."""
    global _SINGLETON, _LOAD_TRIED
    if not flag("AIML_GRADER_ENABLED", True):
        return None
    if _SINGLETON is None and not _LOAD_TRIED:
        _LOAD_TRIED = True
        _SINGLETON = MLGrader.load()
    return _SINGLETON


if __name__ == "__main__":
    # Import through the package so pickled artifact classes bind to
    # core.aiml.grader_ml (not __main__) and reload cleanly at runtime.
    from core.aiml.grader_ml import train_and_save as _train_and_save
    _train_and_save()




