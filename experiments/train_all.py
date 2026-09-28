"""
experiments/train_all.py — one-shot trainer + experiment report for the PLUTO
vProctor classical-AIML layer (MDM AIML requirement 6).

Trains and serializes every named-algorithm model into data/models/, prints the
comparison metric tables (classifier accuracy/macro-F1, regressor R^2/MAE,
clustering silhouette, LDA CV accuracy, Apriori rules, difficulty-regression
R^2/MAE), and writes matplotlib figures to reports/aiml/ for the report/viva:

  grader_classifiers.png   accuracy + macro-F1 per correctness classifier
  grader_confusion.png     confusion matrix of the chosen classifier (held-out)
  grader_regressors.png    R^2 / MAE per continuous-S regressor
  topics_pca_clusters.png  2-D SVD/PCA scatter of the questions by KMeans cluster
  topics_silhouette.png    silhouette per clustering method (KMeans/Agglo/DBSCAN)
  difficulty_scatter.png   authored vs content-predicted irt.b (calibration check)

CPU-only; deterministic seeds, so it is safe to re-run. Reported classifier/
regressor scores are HELD-OUT (train/test split inside each module's train()).

Usage:
    python experiments/train_all.py [all|grader|topics|difficulty]
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib
matplotlib.use("Agg")            # headless: write PNGs, never open a window
import matplotlib.pyplot as plt
import numpy as np


def _out_dir() -> Path:
    out = PROJECT_ROOT / "reports" / "aiml"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _save(fig, path: Path) -> None:
    fig.savefig(path, dpi=120)
    plt.close(fig)
    print(f"    figure -> {path.relative_to(PROJECT_ROOT)}")


# ---- grader (supervised answer correctness) -------------------------------
def run_grader(out: Path) -> dict:
    from core.aiml import grader_ml
    print("=" * 70)
    print("GRADER  — answer correctness: NB / LogReg / LinearSVM / kNN / Tree /")
    print("          RandomForest(Bagging) / AdaBoost(Boosting) classifiers, plus")
    print("          Linear/Ridge/Lasso/ElasticNet/Polynomial/RF/kNN regressors")
    print("          and the shipped Stacking(Ridge+RF+kNN->Ridge) S-emitter.")
    art, metrics = grader_ml.train(verbose=True)
    grader_ml.save(art)
    print(f"[grader] saved -> {grader_ml.artifact_path(grader_ml.GRADER_ARTIFACT)}")
    _plot_grader_classifiers(metrics, out)
    _plot_grader_regressors(metrics, out)
    _plot_grader_confusion(metrics, out)
    return metrics


def _plot_grader_classifiers(metrics: dict, out: Path) -> None:
    clf = metrics["classifiers"]
    names = list(clf.keys())
    acc = [clf[n]["accuracy"] for n in names]
    f1 = [clf[n]["macro_f1"] for n in names]
    x = np.arange(len(names))
    w = 0.4
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(x - w / 2, acc, w, label="accuracy")
    ax.bar(x + w / 2, f1, w, label="macro-F1")
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=30, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("held-out score")
    ax.set_title("Grader classifiers — correct / partial / incorrect")
    ax.legend()
    fig.tight_layout()
    _save(fig, out / "grader_classifiers.png")


def _plot_grader_regressors(metrics: dict, out: Path) -> None:
    reg = metrics["regressors"]
    names = list(reg.keys())
    r2 = [reg[n]["r2"] for n in names]
    mae = [reg[n]["mae"] for n in names]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5))
    a1.bar(names, r2, color="#4C72B0")
    a1.set_title("Regressors - R^2 (continuous S)")
    a1.set_ylabel("R^2")
    a1.set_xticks(range(len(names)))
    a1.set_xticklabels(names, rotation=30, ha="right")
    a2.bar(names, mae, color="#C44E52")
    a2.set_title("Regressors - MAE (continuous S)")
    a2.set_ylabel("MAE")
    a2.set_xticks(range(len(names)))
    a2.set_xticklabels(names, rotation=30, ha="right")
    fig.tight_layout()
    _save(fig, out / "grader_regressors.png")


def _plot_grader_confusion(metrics: dict, out: Path) -> None:
    """Confusion matrix of the chosen classifier on a fresh held-out split
    (the shipped classifier is refit on all rows, so we re-derive an honest
    train/test split here — one classifier fit, deterministic seed)."""
    from sklearn.metrics import confusion_matrix
    from sklearn.model_selection import train_test_split

    from core.aiml import grader_ml
    from core.aiml.features import FeatureExtractor

    name = metrics["chosen"]["classifier"]
    pairs = grader_ml.load_pairs()
    extractor = FeatureExtractor().fit([a for _, a in pairs] + [q for q, _ in pairs])
    rows = grader_ml.build_frame(pairs)
    X, ycls, _ = grader_ml._xy(extractor, rows)
    Xtr, Xte, ytr, yte = train_test_split(
        X, ycls, test_size=0.2, random_state=grader_ml.RANDOM_SEED, stratify=ycls)
    clf = grader_ml._classifiers()[name]
    clf.fit(Xtr, ytr)
    cm = confusion_matrix(yte, clf.predict(Xte))
    labels = [grader_ml.BAND_NAMES[i] for i in sorted(grader_ml.BAND_NAMES)]
    fig, ax = plt.subplots(figsize=(5.6, 5))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    ax.set_xlabel("predicted")
    ax.set_ylabel("true")
    ax.set_title(f"Grader confusion — {name} (held-out)")
    thresh = cm.max() / 2 if cm.max() else 0
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center",
                    color="white" if cm[i, j] > thresh else "black")
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    _save(fig, out / "grader_confusion.png")


# ---- topics (unsupervised structure) --------------------------------------
def run_topics(out: Path) -> dict:
    from core.aiml import topics
    print("=" * 70)
    print("TOPICS  — TF-IDF -> TruncatedSVD(PCA) -> KMeans(partitional) /")
    print("          Agglomerative(hierarchical) / DBSCAN(density); LDA on")
    print("          category; kNN resume ranking; Apriori tag/domain rules.")
    model, metrics = topics.train(verbose=True)
    topics.save(model)
    print(f"[topics] saved -> {topics.artifact_path(topics.TOPICS_ARTIFACT)}")
    _plot_topics_pca(model, out)
    _plot_topics_silhouette(metrics, out)
    return metrics


def _plot_topics_pca(model, out: Path) -> None:
    R = np.asarray(model.reduced)
    labels = np.array([model.cluster.get(q, -1) for q in model.qids])
    fig, ax = plt.subplots(figsize=(8, 6))
    sc = ax.scatter(R[:, 0], R[:, 1], c=labels, cmap="tab10", s=18, alpha=0.85)
    ax.set_xlabel("SVD component 1")
    ax.set_ylabel("SVD component 2")
    ax.set_title(f"Question bank — TF-IDF -> SVD(PCA) 2-D, KMeans clusters "
                 f"(k={len(set(labels.tolist()))})")
    fig.colorbar(sc, ax=ax, label="cluster")
    fig.tight_layout()
    _save(fig, out / "topics_pca_clusters.png")


def _plot_topics_silhouette(metrics: dict, out: Path) -> None:
    cl = metrics["clustering"]
    names = list(cl.keys())
    vals = [(cl[n].get("silhouette") or 0.0) for n in names]
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    ax.bar(names, vals, color=["#4C72B0", "#55A868", "#C44E52"][:len(names)])
    ax.set_ylabel("silhouette (cosine)")
    ax.set_title("Clustering comparison — partitional / hierarchical / density")
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, rotation=12, ha="right")
    for i, v in enumerate(vals):
        ax.text(i, v, f"{v:.3f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    _save(fig, out / "topics_silhouette.png")


# ---- difficulty regression (calibration) ----------------------------------
def run_difficulty(out: Path) -> dict:
    from core.aiml import difficulty_reg as dr
    print("=" * 70)
    print("DIFFICULTY — regression of authored irt.b from question content:")
    print("             Linear/Ridge/Lasso/ElasticNet/Polynomial/RandomForest.")
    art, metrics = dr.train(verbose=True)
    dr.save(art)
    print(f"[difficulty] saved -> {dr.artifact_path(dr.DIFFICULTY_ARTIFACT)}")
    _plot_difficulty(art, metrics, out)
    return metrics


def _plot_difficulty(art, metrics: dict, out: Path) -> None:
    from core.aiml import difficulty_reg as dr
    qs = dr.load_questions()
    X = np.vstack([dr._features(q, art.categories) for q in qs])
    y = np.array([dr._b(q) for q in qs], dtype=float)
    pred = art.model.predict(X)
    fig, ax = plt.subplots(figsize=(6.2, 6))
    ax.scatter(y, pred, s=16, alpha=0.55, color="#4C72B0")
    lo = float(min(y.min(), pred.min()))
    hi = float(max(y.max(), pred.max()))
    ax.plot([lo, hi], [lo, hi], "k--", lw=1, label="authored = predicted")
    ax.set_xlabel("authored irt.b (Elo)")
    ax.set_ylabel("content-predicted irt.b (Elo)")
    chosen = metrics.get("chosen")
    reg = metrics.get("regressors", {}).get(chosen, {})
    ax.set_title(f"Difficulty regression — {chosen} "
                 f"(held-out R^2={reg.get('r2')}, MAE={reg.get('mae')})")
    ax.legend()
    fig.tight_layout()
    _save(fig, out / "difficulty_scatter.png")


# ---- orchestration --------------------------------------------------------
def main(argv) -> int:
    what = (argv[1] if len(argv) > 1 else "all").lower()
    if what not in ("all", "grader", "topics", "difficulty"):
        print(f"unknown target '{what}'; use all|grader|topics|difficulty")
        return 2
    out = _out_dir()
    done = []
    if what in ("all", "grader"):
        run_grader(out)
        done.append("grader")
    if what in ("all", "topics"):
        run_topics(out)
        done.append("topics")
    if what in ("all", "difficulty"):
        run_difficulty(out)
        done.append("difficulty")
    print("\n" + "=" * 70)
    print(f"DONE — trained {', '.join(done)}.")
    print(f"  artifacts -> {(PROJECT_ROOT / 'data' / 'models')}")
    print(f"  figures   -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
