"""
Unsupervised topic structure for PLUTO vProctor (MDM AIML, requirement 2 + 6).

Learns the latent structure of the 432-question bank so the adaptive engine can
reason about "same sub-topic" / "same domain" and so a résumé can be ranked
against questions semantically — all CPU-only scikit-learn.

Named algorithms demonstrated here:
  TF-IDF + Truncated SVD (PCA-style)   vector space over question text+tags
  KMeans (partitional)                 runtime sub-topic label per question
  Agglomerative (hierarchical)         alternative clustering (metrics/plots)
  DBSCAN (density-based)               alternative clustering (metrics/plots)
  LDA (Linear Discriminant Analysis)   supervised category structure + accuracy
  kNN (NearestNeighbors)               résumé-text -> question ranking
  Apriori                              skill/tag co-occurrence association rules

Runtime assignment uses KMeans (it alone has predict); Agglomerative/DBSCAN are
transductive and kept for the experiments module's comparison + silhouette.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from core.aiml import artifact_path, flag

TOPICS_ARTIFACT = "topics.joblib"
N_CLUSTERS = 10
N_COMPONENTS = 50


def load_questions() -> List[dict]:
    """All merged bank questions (curated + generated) via the interview repo."""
    from core.interview.question_bank import get_question_bank
    return get_question_bank().all_questions()


def _doc(q: dict) -> str:
    """Text a question contributes to the TF-IDF space: prompt + tags + category."""
    return " ".join([
        q.get("text", ""),
        " ".join(q.get("tags", []) or []),
        (q.get("category", "") or "").replace("_", " "),
    ]).strip()


def _b(q: dict) -> float:
    return float((q.get("irt") or {}).get("b", 1300))


def apriori(transactions: List[List[str]], min_support: float = 0.02,
            min_conf: float = 0.5, max_len: int = 3) -> Dict:
    """Minimal Apriori (no external dep) over tag/skill transactions.

    Returns frequent itemsets (support >= min_support) up to max_len and the
    association rules A -> B whose confidence >= min_conf, ranked by confidence.
    Used to surface which skills co-occur across the bank (Req 2 structure).
    """
    n = len(transactions)
    if n == 0:
        return {"itemsets": {}, "rules": []}
    tx = [set(t) for t in transactions]

    def support(itemset: frozenset) -> float:
        return sum(1 for t in tx if itemset <= t) / n

    # L1
    items = sorted({i for t in tx for i in t})
    freq: Dict[frozenset, float] = {}
    current = [frozenset([i]) for i in items]
    k = 1
    while current and k <= max_len:
        kept = {}
        for cand in current:
            s = support(cand)
            if s >= min_support:
                kept[cand] = s
        freq.update(kept)
        # generate (k+1)-candidates from the kept k-itemsets (self-join)
        base = list(kept.keys())
        nxt = set()
        for a in range(len(base)):
            for b in range(a + 1, len(base)):
                union = base[a] | base[b]
                if len(union) == k + 1:
                    nxt.add(union)
        current = list(nxt)
        k += 1

    rules = []
    for itemset, s in freq.items():
        if len(itemset) < 2:
            continue
        for r in range(1, len(itemset)):
            for ante in combinations(sorted(itemset), r):
                ante = frozenset(ante)
                cons = itemset - ante
                sa = freq.get(ante) or support(ante)
                if sa <= 0:
                    continue
                conf = s / sa
                if conf >= min_conf:
                    rules.append({
                        "antecedent": sorted(ante), "consequent": sorted(cons),
                        "support": round(s, 4), "confidence": round(conf, 4)})
    rules.sort(key=lambda x: (x["confidence"], x["support"]), reverse=True)
    itemsets = {",".join(sorted(k)): round(v, 4) for k, v in freq.items()}
    return {"itemsets": itemsets, "rules": rules}


@dataclass
class TopicModel:
    """Fitted TF-IDF + SVD + KMeans + LDA + kNN index, serialized as one file."""
    vectorizer: object
    svd: object
    kmeans: object
    lda: object
    nn: object                    # sklearn NearestNeighbors over the SVD space
    qids: List[str]               # row order of `reduced`
    reduced: np.ndarray           # SVD-reduced question vectors (for kNN + plots)
    cluster: Dict[str, int]       # qid -> KMeans cluster
    category: Dict[str, str]      # qid -> category (the "domain")
    bval: Dict[str, float]        # qid -> irt.b difficulty
    metrics: Dict
    rules: List

    # ---- runtime queries ---------------------------------------------------
    def _vec(self, text: str) -> np.ndarray:
        return self.svd.transform(self.vectorizer.transform([text or ""]))

    def cluster_of(self, qid: str) -> int:
        return self.cluster.get(qid, -1)

    def same_cluster(self, a: str, b: str) -> bool:
        return a in self.cluster and self.cluster.get(a) == self.cluster.get(b)

    def rank_by_resume(self, resume_text: str, candidate_ids: Optional[List[str]] = None,
                       k: Optional[int] = None) -> List[str]:
        """kNN ranking of questions by semantic closeness to the résumé text."""
        if not self.qids:
            return []
        vec = self._vec(resume_text)
        n = len(self.qids)
        dist, idx = self.nn.kneighbors(vec, n_neighbors=n)
        ranked = [self.qids[i] for i in idx[0]]
        if candidate_ids is not None:
            allow = set(candidate_ids)
            ranked = [q for q in ranked if q in allow]
        return ranked[:k] if k else ranked

    def same_domain_neighbors(self, qid: str, candidate_ids: List[str],
                              easier_than_b: Optional[float] = None) -> List[str]:
        """Questions in candidate_ids sharing qid's DOMAIN (category), optionally
        strictly easier (irt.b below easier_than_b). Ordered: same KMeans cluster
        first, then nearest difficulty. This is the "similar easier question of
        the same domain" primitive the search-based selector builds on."""
        dom = self.category.get(qid)
        if dom is None:
            return []
        anchor_b = self.bval.get(qid, 1300)
        out = []
        for cid in candidate_ids:
            if cid == qid or self.category.get(cid) != dom:
                continue
            if easier_than_b is not None and self.bval.get(cid, 1300) >= easier_than_b:
                continue
            out.append(cid)
        out.sort(key=lambda c: (0 if self.same_cluster(qid, c) else 1,
                                abs(self.bval.get(c, 1300) - anchor_b)))
        return out

RANDOM_SEED = 13


def train(verbose: bool = True) -> Tuple["TopicModel", Dict]:
    """Fit the whole topic stack over the merged bank and collect comparison
    metrics (SVD explained variance, per-method silhouette, LDA CV accuracy,
    Apriori rules). Returns (model, metrics)."""
    from collections import Counter

    from sklearn.cluster import DBSCAN, AgglomerativeClustering, KMeans
    from sklearn.decomposition import TruncatedSVD
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics import accuracy_score, silhouette_score
    from sklearn.model_selection import cross_val_score
    from sklearn.neighbors import NearestNeighbors

    qs = load_questions()
    qids = [q["id"] for q in qs]
    docs = [_doc(q) for q in qs]
    cats = [q.get("category", "unknown") for q in qs]

    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2),
                                 min_df=2, sublinear_tf=True)
    X = vectorizer.fit_transform(docs)
    n_comp = max(2, min(N_COMPONENTS, X.shape[1] - 1, X.shape[0] - 1))
    svd = TruncatedSVD(n_components=n_comp, random_state=RANDOM_SEED)
    reduced = svd.fit_transform(X)

    k = max(2, min(N_CLUSTERS, len(qs) - 1))
    kmeans = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_SEED).fit(reduced)
    agglo = AgglomerativeClustering(n_clusters=k).fit(reduced)
    db = DBSCAN(eps=0.5, min_samples=4, metric="cosine").fit(reduced)

    def _sil(labels) -> Optional[float]:
        if len(set(labels) - {-1}) < 2:
            return None
        try:
            return round(float(silhouette_score(reduced, labels, metric="cosine")), 4)
        except Exception:
            return None

    metrics: Dict = {
        "n_questions": len(qs), "n_features": int(X.shape[1]), "svd_components": n_comp,
        "explained_variance": round(float(svd.explained_variance_ratio_.sum()), 4),
        "clustering": {
            "KMeans(partitional)": {"k": k, "silhouette": _sil(kmeans.labels_)},
            "Agglomerative(hierarchical)": {"k": k, "silhouette": _sil(agglo.labels_)},
            "DBSCAN(density)": {"clusters": len(set(db.labels_) - {-1}),
                                "noise": int((db.labels_ == -1).sum()),
                                "silhouette": _sil(db.labels_)},
        }}
    # LDA (supervised) on category — keeps only categories with enough members.
    lda = None
    lda_acc = None
    cc = Counter(cats)
    keep = [i for i, c in enumerate(cats) if cc[c] >= 3]
    ykeep = [cats[i] for i in keep]
    if len(set(ykeep)) >= 2:
        Xl = reduced[keep]
        lda = LinearDiscriminantAnalysis().fit(Xl, ykeep)
        try:
            cv = cross_val_score(LinearDiscriminantAnalysis(), Xl, ykeep, cv=3)
            lda_acc = round(float(cv.mean()), 4)
        except Exception:
            lda_acc = round(float(accuracy_score(ykeep, lda.predict(Xl))), 4)
    metrics["lda_cv_accuracy"] = lda_acc

    nn = NearestNeighbors(metric="cosine").fit(reduced)
    # Apriori over baskets of {skill tags} + {the question's domain}, so it can
    # surface skill<->skill and skill->domain associations (Req 2 routing). Tags
    # alone are too sparse (most questions carry a single tag).
    transactions = [list(set(q.get("tags", []) or [])) + ["dom:" + q.get("category", "?")]
                    for q in qs]
    rules = apriori(transactions, min_support=0.01, min_conf=0.5, max_len=3)
    metrics["apriori"] = {"n_rules": len(rules["rules"]), "top": rules["rules"][:8]}


    model = TopicModel(
        vectorizer=vectorizer, svd=svd, kmeans=kmeans, lda=lda, nn=nn,
        qids=qids, reduced=reduced,
        cluster={qid: int(l) for qid, l in zip(qids, kmeans.labels_)},
        category={qid: c for qid, c in zip(qids, cats)},
        bval={q["id"]: _b(q) for q in qs},
        metrics=metrics, rules=rules["rules"])
    if verbose:
        _print_metrics(metrics)
    return model, metrics


def _print_metrics(m: Dict) -> None:
    print(f"\n[topics] {m['n_questions']} questions, {m['n_features']} tf-idf features "
          f"-> {m['svd_components']} SVD comps (explained var {m['explained_variance']})")
    for name, s in m["clustering"].items():
        print(f"    {name:<30} {s}")
    print(f"    LDA 3-fold CV accuracy (category): {m['lda_cv_accuracy']}")
    print(f"    Apriori rules: {m['apriori']['n_rules']} "
          f"(top-{len(m['apriori']['top'])} kept)")

def save(model: "TopicModel", path: Optional[Path] = None) -> Path:
    import joblib
    p = Path(path) if path else artifact_path(TOPICS_ARTIFACT)
    p.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, p)
    return p


def train_and_save(path: Optional[Path] = None, verbose: bool = True):
    model, metrics = train(verbose=verbose)
    p = save(model, path)
    if verbose:
        print(f"[topics] saved -> {p}")
    return p, metrics


_SINGLETON: Optional[TopicModel] = None
_LOAD_TRIED = False


def get_topic_model() -> Optional[TopicModel]:
    """Lazy singleton; None when the flag is off or no artifact exists."""
    global _SINGLETON, _LOAD_TRIED
    if not flag("AIML_TOPICS_ENABLED", True):
        return None
    if _SINGLETON is None and not _LOAD_TRIED:
        _LOAD_TRIED = True
        import joblib
        p = artifact_path(TOPICS_ARTIFACT)
        if p.exists():
            try:
                _SINGLETON = joblib.load(p)
            except Exception:
                _SINGLETON = None
    return _SINGLETON


if __name__ == "__main__":
    from core.aiml.topics import train_and_save as _train_and_save
    _train_and_save()





