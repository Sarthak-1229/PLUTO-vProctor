"""Enrich questions with NLP metadata, domains, skills, clusters, difficulty, and embeddings.

Implements Section 2B.2 of docs/spec/2B-dataset.md.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import numpy as np

# Ensure workspace root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.app.algorithms.keyword_extraction import rake_keywords
from backend.app.algorithms.similarity import TFIDFVectorizer

PROCESSED_DIR = ROOT_DIR / "backend" / "app" / "data" / "processed"
CLEAN_FILE = PROCESSED_DIR / "qa_clean.jsonl"
TAXONOMY_FILE = ROOT_DIR / "backend" / "app" / "data" / "skills_taxonomy.json"
JOBS_FILE = ROOT_DIR / "backend" / "app" / "data" / "jobs.json"
QUESTIONS_OUT = PROCESSED_DIR / "questions.json"
EMBEDDINGS_OUT = PROCESSED_DIR / "embeddings.npy"
EMBEDDINGS_IDS_OUT = PROCESSED_DIR / "embeddings_ids.json"

DOMAINS = [
    "Security",
    "Cloud",
    "DevOps/SRE",
    "Databases",
    "Data Science/ML",
    "Bioinformatics",
    "Blockchain",
    "Web Development",
    "OOP/Software Design",
    "Data Structures and Algorithms",
    "Operating Systems/Networks",
    "General",
]

DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "Security": [
        "security", "vulnerability", "encryption", "cipher", "tls", "ssl", "auth",
        "zero trust", "ids", "ips", "firewall", "xss", "csrf", "injection", "siem",
        "soar", "attack", "malware", "phishing", "rbac", "jwt", "oauth", "hashing"
    ],
    "Cloud": [
        "aws", "azure", "gcp", "cloud", "ec2", "s3", "lambda", "serverless",
        "iaas", "paas", "saas", "vpc", "iam", "cloudwatch", "multi-tenant"
    ],
    "DevOps/SRE": [
        "docker", "kubernetes", "k8s", "container", "ci/cd", "pipeline", "jenkins",
        "istio", "helm", "prometheus", "grafana", "elk", "logstash", "kibana",
        "canary", "blue-green", "slo", "sla", "sli", "telemetry", "devops", "sre"
    ],
    "Databases": [
        "sql", "rdbms", "database", "postgres", "postgresql", "mysql", "nosql",
        "mongodb", "redis", "cassandra", "acid", "index", "sharding", "replication",
        "transaction", "query", "normalization", "cap theorem", "schema"
    ],
    "Data Science/ML": [
        "machine learning", "deep learning", "neural network", "model", "training",
        "regression", "classification", "clustering", "nlp", "computer vision",
        "data drift", "confusion matrix", "precision", "recall", "gradient",
        "overfitting", "feature", "dataset", "supervised", "unsupervised", "cnn"
    ],
    "Bioinformatics": [
        "genome", "genomic", "variant calling", "dna", "rna", "sequencing",
        "bioinformatics", "indels", "fasta", "fastq", "alignment", "pathway",
        "chromosome", "mutation", "gene", "blast", "vcf"
    ],
    "Blockchain": [
        "blockchain", "crypto", "smart contract", "consensus", "ethereum",
        "solidity", "51% attack", "proof of work", "proof of stake", "distributed ledger",
        "decentralized", "token", "mining"
    ],
    "Web Development": [
        "css", "html", "javascript", "react", "typescript", "frontend", "dom",
        "viewport", "flexbox", "grid", "browser", "rest api", "endpoint", "http",
        "json", "tailwind", "webpack", "vite", "web"
    ],
    "OOP/Software Design": [
        "java", "oop", "object-oriented", "design pattern", "solid", "singleton",
        "factory", "observer", "strategy", "inheritance", "polymorphism",
        "encapsulation", "interface", "abstract class", "coupling", "cohesion"
    ],
    "Data Structures and Algorithms": [
        "algorithm", "data structure", "binary tree", "graph", "sorting", "searching",
        "dynamic programming", "time complexity", "big o", "space complexity",
        "heap", "hash table", "linked list", "recursion", "dijkstra", "traversal"
    ],
    "Operating Systems/Networks": [
        "operating system", "linux", "kernel", "process", "thread", "concurrency",
        "deadlock", "banker's algorithm", "semaphore", "mutex", "tcp", "udp",
        "ip", "dns", "socket", "packet", "subnet", "virtual memory", "paging"
    ],
}


def classify_type(q: str) -> str:
    """Classify question type based on opening pattern."""
    q_low = q.lower().strip()
    if re.search(r"^(implement|write |code |build |design a class|create a function)", q_low):
        return "coding"
    if re.search(r"(difference between| vs | vs\. |compare|contrast|versus)", q_low):
        return "compare"
    if re.search(r"^(when would|what happens if|in case of|how would you handle)", q_low):
        return "scenario"
    if re.search(r"^(how |why |in what way)", q_low):
        return "how_why"
    if re.search(r"^(explain|describe|discuss|overview of|give an overview)", q_low):
        return "explain"
    if re.search(r"^(what is|what are|define |what does|meaning of)", q_low):
        return "definition"
    return "explain"


def is_spoken_ok(q_type: str, question: str) -> bool:
    """Determine if question is suitable for a spoken/voice interview."""
    if q_type == "coding":
        return False
    q_low = question.lower()
    if any(phrase in q_low for phrase in ["write code", "write a query", "draw a", "diagram", "implement code"]):
        return False
    return True


def estimate_duration_seconds(q_type: str, difficulty: int) -> int:
    """Estimate expected answer time in seconds."""
    base = {
        "definition": 45,
        "explain": 70,
        "how_why": 90,
        "compare": 90,
        "scenario": 100,
        "coding": 180,
    }.get(q_type, 70)
    # Add modest delta for higher difficulty
    return base + (difficulty - 1) * 15


def match_skills(text: str, taxonomy: List[Dict[str, Any]]) -> List[str]:
    """Match skills against taxonomy via keywords and aliases."""
    text_low = " " + text.lower() + " "
    matched = []
    for skill in taxonomy:
        name = skill["name"]
        triggers = [name.lower()] + [a.lower() for a in skill.get("aliases", [])] + [k.lower() for k in skill.get("keywords", [])]
        for trig in triggers:
            pattern = r"(?<![a-zA-Z0-9])" + re.escape(trig) + r"(?![a-zA-Z0-9])"
            if re.search(pattern, text_low):
                matched.append(name)
                break
    return matched


def score_domain_rules(text: str) -> Tuple[str, float]:
    """Score domain based on curated domain keyword frequencies."""
    text_low = text.lower()
    scores = Counter()
    for domain, kws in DOMAIN_KEYWORDS.items():
        for kw in kws:
            pattern = r"(?<![a-zA-Z0-9])" + re.escape(kw) + r"(?![a-zA-Z0-9])"
            matches = len(re.findall(pattern, text_low))
            if matches:
                scores[domain] += matches

    if not scores:
        return "General", 0.0

    best_domain, best_score = scores.most_common(1)[0]
    total = sum(scores.values())
    confidence = best_score / total
    return best_domain, confidence


def compute_difficulty_score(q: str, a: str) -> float:
    """Compute continuous heuristic difficulty score."""
    q_low = q.lower()
    a_len = len(a.split())
    depth_terms = ["trade-off", "trade off", "architecture", "strategy", "consensus", "internals", "scalability", "concurrency", "distributed", "optimization"]
    depth_count = sum(1 for term in depth_terms if term in q_low or term in a.lower())
    acronyms = len(re.findall(r"\b[A-Z]{2,5}\b", q + " " + a))

    # Score components
    score = (a_len / 20.0) + (depth_count * 1.5) + (acronyms * 0.4)
    return score


def main():
    print("=== PLUTO vProctor: Question Enrichment Pipeline ===")

    if not CLEAN_FILE.exists():
        print(f"Error: {CLEAN_FILE} does not exist. Run ingest_datasets.py first!")
        sys.exit(1)

    with open(CLEAN_FILE, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    print(f"Loaded {len(records)} clean questions from {CLEAN_FILE}")

    # Load taxonomy
    taxonomy = []
    if TAXONOMY_FILE.exists():
        with open(TAXONOMY_FILE, "r", encoding="utf-8") as f:
            taxonomy = json.load(f).get("skills", [])
        print(f"Loaded {len(taxonomy)} skills from {TAXONOMY_FILE}")

    # 1. Type and Spoken_OK
    for r in records:
        r["type"] = classify_type(r["question"])
        r["spoken_ok"] = is_spoken_ok(r["type"], r["question"])

    # 2. Skills extraction
    for r in records:
        combined_text = r["question"] + " " + r["answer"]
        r["skills"] = match_skills(combined_text, taxonomy)

    # 3. Domain classification (Rule-based pseudo-labels + ML training)
    train_texts = []
    train_labels = []
    rule_results = []

    for r in records:
        combined = r["question"] + " " + r["answer"]
        domain, conf = score_domain_rules(combined)
        rule_results.append((domain, conf))
        if r["split"] == "train" and conf >= 0.5 and domain != "General":
            train_texts.append(combined)
            train_labels.append(domain)

    print(f"High-confidence training examples for domain classifier: {len(train_texts)}")

    # Train MultinomialNB + LogisticRegression on train split
    from sklearn.feature_extraction.text import TfidfVectorizer as SkTfidf
    from sklearn.naive_bayes import MultinomialNB
    from sklearn.linear_model import LogisticRegression

    clf_tfidf = SkTfidf(max_features=2500, stop_words="english", ngram_range=(1, 2))
    X_train = clf_tfidf.fit_transform(train_texts)
    domain_clf = LogisticRegression(max_iter=500, C=2.0)
    domain_clf.fit(X_train, train_labels)

    # Predict domains for all records
    all_texts = [r["question"] + " " + r["answer"] for r in records]
    X_all = clf_tfidf.transform(all_texts)
    predicted_domains = domain_clf.predict(X_all)
    predicted_probs = domain_clf.predict_proba(X_all).max(axis=1)

    for i, r in enumerate(records):
        rule_domain, rule_conf = rule_results[i]
        # If rules were high confidence (>= 0.7), trust rules; otherwise take ML prediction
        if rule_conf >= 0.7:
            r["domain"] = rule_domain
        else:
            r["domain"] = predicted_domains[i]

    # 4. Difficulty (1, 2, 3 terciles)
    diff_scores = [compute_difficulty_score(r["question"], r["answer"]) for r in records]
    t1, t2 = np.percentile(diff_scores, [33.3, 66.7])

    for i, r in enumerate(records):
        score = diff_scores[i]
        if score <= t1:
            diff = 1
        elif score <= t2:
            diff = 2
        else:
            diff = 3
        r["difficulty"] = diff
        r["est_seconds"] = estimate_duration_seconds(r["type"], diff)

    # 5. Expected Keywords (RAKE on reference answer)
    for r in records:
        kw_tuples = rake_keywords(r["answer"], top_n=6)
        r["expected_keywords"] = [kw for kw, _ in kw_tuples]
        r["ideal_answer_summary"] = r["answer"]

    # 6. MiniLM Embeddings & K-Means Clustering
    print("\nLoading SentenceTransformer 'all-MiniLM-L6-v2' on CPU...")
    from sentence_transformers import SentenceTransformer
    from sklearn.cluster import KMeans

    model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
    q_and_a_texts = [f"Question: {r['question']} Answer: {r['answer']}" for r in records]

    print("Encoding all question-answer pairs into embeddings (batch_size=64)...")
    embeddings = model.encode(q_and_a_texts, batch_size=64, show_progress_bar=False, normalize_embeddings=True)

    # Save embeddings
    np.save(EMBEDDINGS_OUT, embeddings)
    qid_list = [r["id"] for r in records]
    with open(EMBEDDINGS_IDS_OUT, "w", encoding="utf-8") as f:
        json.dump(qid_list, f)
    print(f"Saved embeddings shape {embeddings.shape} to {EMBEDDINGS_OUT}")

    # Cluster using KMeans on train embeddings
    k_clusters = 24
    kmeans = KMeans(n_clusters=k_clusters, random_state=42, n_init=10)
    cluster_labels = kmeans.fit_predict(embeddings)

    for i, r in enumerate(records):
        r["cluster_id"] = int(cluster_labels[i])

    # Write enriched questions to questions.json
    with open(QUESTIONS_OUT, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {len(records)} enriched questions to {QUESTIONS_OUT}")

    # Print Coverage Table
    print("\n" + "=" * 80)
    print(f"{'PLUTO vProctor: Dataset Coverage Table':^80}")
    print("=" * 80)

    domain_counts = Counter(r["domain"] for r in records)
    domain_spoken = Counter(r["domain"] for r in records if r["spoken_ok"])
    type_counts = Counter(r["type"] for r in records)
    diff_counts = Counter(r["difficulty"] for r in records)
    split_counts = Counter(r["split"] for r in records)

    print("\n[Questions by Domain]")
    print(f"{'Domain':<35} | {'Total':<8} | {'Spoken OK':<10}")
    print("-" * 58)
    for dom in sorted(DOMAINS):
        print(f"{dom:<35} | {domain_counts[dom]:<8} | {domain_spoken[dom]:<10}")

    print("\n[Questions by Type]")
    for t, c in type_counts.most_common():
        print(f"  {t:<15}: {c}")

    print("\n[Questions by Difficulty]")
    for d in [1, 2, 3]:
        print(f"  Level {d}: {diff_counts[d]}")

    print("\n[Questions by Split]")
    for sp in ["train", "val", "test"]:
        print(f"  {sp:<10}: {split_counts[sp]}")

    # Verify Job Profiles Coverage (must have >= 25 spoken_ok questions)
    print("\n" + "=" * 80)
    print("Checking Job Profiles Usable Question Counts (Threshold >= 25):")
    print("-" * 80)

    if JOBS_FILE.exists():
        with open(JOBS_FILE, "r", encoding="utf-8") as jf:
            jobs_data = json.load(jf).get("jobs", [])
        for job in jobs_data:
            j_id = job["id"]
            j_title = job["title"]
            j_domains = set(job["question_domains"])
            # Match questions in job domains that are spoken_ok
            matching_q = [r for r in records if r["spoken_ok"] and r["domain"] in j_domains]
            status = "PASS" if len(matching_q) >= 25 else "FAIL"
            print(f"[{status}] {j_title[:38]:<38} (Domains: {', '.join(j_domains)}): {len(matching_q)} questions")
            if len(matching_q) < 25:
                raise ValueError(f"Job {j_id} has only {len(matching_q)} questions (< 25)!")
    print("=" * 80)
    print("Phase 2 Enrichment completed successfully!")


if __name__ == "__main__":
    main()
