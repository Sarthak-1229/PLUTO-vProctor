"""
Offline enrichment build tool for PLUTO vProctor (dataset -> question bank).

Turns the flat imported Q&A dataset (data/{train,val,test}.jsonl under the
archive: only {"question","answer"}) into schema-valid bank items and writes
them to data/question_bank_generated.json, which QuestionBank merges at load.
The curated data/question_bank.json is never touched.

HYBRID enrichment (the user's chosen strategy):
  * heuristics fill the MECHANICAL fields (id, irt.b seed from tier, role_fit,
    scoring_rubric, expected_answer_seconds, provenance);
  * local qwen2.5:7b (reusing judge_llm.py's Ollama structured-output pattern:
    format=<schema>, temperature 0, pydantic-validated, one retry) fills the
    SEMANTIC fields (category, type, difficulty, keywords, ideal_answer_points,
    tags) from the question + its reference answer.

BALANCED subset: dedup (within dataset + against the curated bank) + noise
filter, a cheap heuristic pre-classify + quality score, then keep only the
top-N per (approximate) category so we enrich a few hundred items, not ~18x the
bank. tech_security gets the largest cap but is still bounded.

Resumable: every LLM result is cached by question hash in a sidecar, so a
re-run (or one resumed after Ctrl-C) skips work already done.

Usage:
  python scripts/enrich_dataset.py --dry-run          # size the workload, no LLM
  python scripts/enrich_dataset.py                    # hybrid build (needs Ollama)
  python scripts/enrich_dataset.py --heuristic-only   # no LLM at all (fallback)
"""
import argparse
import hashlib
import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("enrich")

# ---------------------------------------------------------------------------
# Paths (script lives in PLUTO-vProctor/scripts/)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]          # PLUTO-vProctor/
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_DATASET_DIR = PROJECT_ROOT.parent / "archive" / "data"
CURATED_BANK = DATA_DIR / "question_bank.json"
OUT_PATH = DATA_DIR / "question_bank_generated.json"
CACHE_PATH = DATA_DIR / ".enrich_cache.json"

OLLAMA_HOST = "http://127.0.0.1:11434"
LLM_MODEL = "qwen2.5:7b"

# Authored difficulty tier -> Elo b seed. Mirrors question_bank.TIER_TO_B
# (kept local so this build tool has no import coupling to the runtime engine).
TIER_TO_B = {1: 1000, 2: 1150, 3: 1300, 4: 1450, 5: 1600}

# category -> id prefix. Existing prefixes match the curated bank; generated ids
# start at 500 so they can never collide with the curated (<100) numbering.
CATEGORY_PREFIX = {
    "behavioral": "beh", "hr_culture": "hr", "situational": "sit",
    "aptitude": "apt", "tech_cs_fundamentals": "cs", "tech_backend": "be",
    "tech_frontend": "fe", "tech_data_ml": "dml", "tech_system_design": "sd",
    "tech_pm": "pm", "tech_security": "sec",
}
CATEGORIES = list(CATEGORY_PREFIX.keys())
ID_START = 500

# Valid taxonomy skill slugs generated tags are filtered to (so select_for_resume
# tag_overlap actually matches resume-derived slugs). Includes the new `security`.
VALID_TAGS = {
    "python", "java", "javascript", "react", "sql", "nosql", "rest-api",
    "system-design", "data-structures", "machine-learning", "statistics",
    "docker", "product-strategy", "communication", "security",
}
CATEGORY_DEFAULT_TAGS = {
    "behavioral": ["communication"], "hr_culture": ["communication"],
    "situational": ["communication"], "aptitude": ["data-structures"],
    "tech_cs_fundamentals": ["data-structures"], "tech_backend": ["rest-api"],
    "tech_frontend": ["react"], "tech_data_ml": ["machine-learning"],
    "tech_system_design": ["system-design"], "tech_pm": ["product-strategy"],
    "tech_security": ["security"],
}
CATEGORY_DEFAULT_TYPE = {
    "behavioral": "behavioral", "hr_culture": "behavioral",
    "situational": "situational", "aptitude": "technical",
    "tech_cs_fundamentals": "conceptual", "tech_backend": "technical",
    "tech_frontend": "technical", "tech_data_ml": "conceptual",
    "tech_system_design": "technical", "tech_pm": "conceptual",
    "tech_security": "technical",
}
VALID_TYPES = {"behavioral", "technical", "situational", "conceptual"}

# ---------------------------------------------------------------------------
# Cheap heuristic pre-classifier (only used to BALANCE/CAP before the LLM step;
# the LLM later confirms/overrides the category on the kept candidates).
# ---------------------------------------------------------------------------
CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "tech_security": [
        "security", "vulnerab", "encrypt", "decrypt", "oauth", "token", "threat",
        "attack", "exploit", "firewall", " iam ", "authentic", "authoriz", "cve",
        "owasp", "malware", "phishing", "ransomware", "zero trust", "tls", "ssl",
        "certificate", "penetration", "cloud security", "siem", "cryptograph",
        "xss", "csrf", "sql injection", "ddos", "mfa", "rbac", "secret", "kms",
        "waf", "hashing", "breach", "compliance", "audit", "confidential",
        "cyber", "intrusion", "sanitiz", "privilege",
    ],
    "tech_system_design": [
        "design a system", "scalab", "load balanc", "distributed", "sharding",
        "partition", "throughput", "latency", "availability", "cap theorem",
        "consensus", "replication", "message queue", "microservice", "caching layer",
        "high availability", "fault tolerance", "rate limit", "architecture",
    ],
    "tech_data_ml": [
        "machine learning", "neural", "gradient", "regression", "classifier",
        "classification", "dataset", "feature", "overfit", "underfit", "precision",
        "recall", "embedding", "transformer", "clustering", "training data",
        "supervised", "unsupervised", "deep learning", "loss function", "model",
        "inference", "hyperparameter", "cross-validation",
    ],
    "tech_frontend": [
        "react", "css", " dom", "browser", "component", "render", "html",
        " ui ", "hooks", "virtual dom", "layout", "flexbox", "responsive",
        "state management", "javascript event", "webpack",
    ],
    "tech_backend": [
        "api", "database", "server", "rest", "endpoint", "orm", "transaction",
        "http", "sql", "index", "query", "cache", "backend", "microservice",
        "queue", "webhook", "session", "middleware",
    ],
    "tech_cs_fundamentals": [
        "algorithm", "data structure", "complexity", "big o", "sorting", "tree",
        "graph", "recursion", "hash", "stack", "queue", "context switch",
        "process", "thread", "deadlock", "pointer", "operating system",
        "compiler", "linked list", "binary search",
    ],
    "aptitude": [
        "implement ", "write a function", "write code", "code a ", "leetcode",
        "puzzle", "probability that", "how many ways",
    ],
    "tech_pm": [
        "product", "roadmap", "prioriti", "stakeholder", "feature", "user story",
        "kpi", "metric", "launch", "go-to-market", "backlog", "mvp",
    ],
    "behavioral": [
        "tell me about a time", "describe a time", "give an example of a time",
        "a situation where you", "how did you handle",
    ],
    "hr_culture": [
        "why do you want", "your strengths", "your weakness", "see yourself in",
        "salary", "why should we hire", "culture", "leave your", "career goal",
    ],
    "situational": [
        "what would you do if", "how would you handle a situation", "imagine you",
        "suppose you", "if a teammate", "if your manager",
    ],
}
DEFAULT_CATEGORY = "tech_cs_fundamentals"   # dataset is technical-heavy


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _words(text: str) -> List[str]:
    return re.findall(r"[a-z0-9+#]+", (text or "").lower())


def pre_classify(question: str, answer: str) -> str:
    """Approximate category by keyword hits (padded with spaces for word-ish match)."""
    blob = " " + _norm(question + " . " + answer) + " "
    best, best_score = DEFAULT_CATEGORY, 0
    for cat, kws in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in kws if kw in blob)
        # Security signals are strong; give them a slight edge on ties.
        if cat == "tech_security" and score:
            score += 0.5
        if score > best_score:
            best, best_score = cat, score
    return best


def quality_score(question: str, answer: str) -> float:
    """Prefer specific, substantial (but not run-on) answers. Range ~[0,1]."""
    aw = _words(answer)
    n = len(aw)
    length = min(n, 40) / 40.0                       # rewards up to ~40 words
    uniq = (len(set(aw)) / n) if n else 0.0          # penalizes repetition
    specific = 0.0
    if re.search(r"\d", answer):
        specific += 0.5                              # numbers / versions
    if re.search(r"[A-Z]{2,}", answer):
        specific += 0.5                              # acronyms (TLS, IAM, CPU)
    return 0.6 * length + 0.25 * uniq + 0.15 * min(specific, 1.0)


def load_dataset(dataset_dir: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for name in ("train.jsonl", "val.jsonl", "test.jsonl"):
        p = dataset_dir / name
        if not p.exists():
            logger.warning("Dataset split missing: %s", p)
            continue
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                q, a = rec.get("question", ""), rec.get("answer", "")
                if q and a:
                    rows.append({"question": q.strip(), "answer": a.strip()})
    return rows


def curated_question_norms() -> set:
    if not CURATED_BANK.exists():
        return set()
    with open(CURATED_BANK, "r", encoding="utf-8") as f:
        bank = json.load(f)
    return {_norm(q.get("text", "")) for q in bank.get("questions", [])}


def clean_and_dedup(rows: List[Dict[str, str]]) -> Tuple[List[dict], Dict[str, int]]:
    """Drop noise + duplicates (within dataset and vs the curated bank).

    Returns (candidates, stats). Each candidate gains approx_category + quality.
    """
    curated = curated_question_norms()
    seen: set = set()
    kept: List[dict] = []
    stats = {"raw": len(rows), "dup_dataset": 0, "dup_curated": 0,
             "too_short_q": 0, "too_short_a": 0, "run_on": 0}
    for r in rows:
        q, a = r["question"], r["answer"]
        qn = _norm(q)
        qwords, awords = _words(q), _words(a)
        if len(qwords) < 3:
            stats["too_short_q"] += 1
            continue
        if len(awords) < 7:
            stats["too_short_a"] += 1
            continue
        if len(qwords) > 60 or len(awords) > 120:      # word-salad / run-on
            stats["run_on"] += 1
            continue
        if qn in curated:
            stats["dup_curated"] += 1
            continue
        if qn in seen:
            stats["dup_dataset"] += 1
            continue
        seen.add(qn)
        kept.append({
            "question": q, "answer": a,
            "approx_category": pre_classify(q, a),
            "quality": quality_score(q, a),
        })
    stats["kept"] = len(kept)
    return kept, stats


def balance(candidates: List[dict], cap: int, security_cap: int) -> List[dict]:
    """Keep the top-N by quality within each approximate category."""
    buckets: Dict[str, List[dict]] = {}
    for c in candidates:
        buckets.setdefault(c["approx_category"], []).append(c)
    selected: List[dict] = []
    for cat, items in buckets.items():
        items.sort(key=lambda c: c["quality"], reverse=True)
        limit = security_cap if cat == "tech_security" else cap
        selected.extend(items[:limit])
    return selected


# ---------------------------------------------------------------------------
# Semantic enrichment (LLM) — reuses judge_llm.py's structured-output pattern.
# ---------------------------------------------------------------------------
ENRICH_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": CATEGORIES},
        "type": {"type": "string", "enum": sorted(VALID_TYPES)},
        "difficulty": {"type": "integer", "minimum": 1, "maximum": 5},
        "keywords": {"type": "array", "items": {"type": "string"}},
        "ideal_answer_points": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["category", "type", "difficulty", "keywords", "ideal_answer_points"],
}

ENRICH_SYSTEM = (
    "You convert a short interview question and its reference answer into "
    "structured metadata for a question bank. Be accurate, concise, and faithful "
    "to the reference answer. Respond with JSON only, matching the schema."
)

_STOP = {"the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for",
         "with", "is", "are", "be", "as", "at", "by", "it", "this", "that",
         "you", "your", "we", "they", "how", "what", "why", "when", "which",
         "from", "can", "will", "its", "their", "these", "those", "into"}


def _build_enrich_prompt(question: str, answer: str, approx: str) -> str:
    payload = {
        "question": question,
        "reference_answer": answer,
        "allowed_categories": CATEGORIES,
        "allowed_types": sorted(VALID_TYPES),
        "allowed_tags": sorted(VALID_TAGS),
        "approx_category_hint": approx,
    }
    return (
        "Produce metadata for this interview item:\n"
        "- category: the single best fit from allowed_categories (use "
        "tech_security for security/cloud-security/auth/crypto topics).\n"
        "- type: one of allowed_types.\n"
        "- difficulty: integer 1 (basic recall) .. 5 (expert/deep).\n"
        "- keywords: 3-8 lowercase technical terms a correct answer should contain.\n"
        "- ideal_answer_points: 3-6 atomic, checkable concepts decomposed from the "
        "reference answer (each a short standalone phrase).\n"
        "- tags: 1-4 slugs chosen ONLY from allowed_tags.\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def _sanitize_semantic(raw: dict, cand: dict) -> dict:
    """Coerce LLM output into valid, non-empty semantic fields (with fallbacks)."""
    approx = cand["approx_category"]
    cat = raw.get("category")
    if cat not in CATEGORIES:
        cat = approx
    typ = raw.get("type")
    if typ not in VALID_TYPES:
        typ = CATEGORY_DEFAULT_TYPE.get(cat, "technical")
    try:
        diff = int(raw.get("difficulty", 3))
    except (TypeError, ValueError):
        diff = 3
    diff = max(1, min(5, diff))

    kws = [str(k).strip().lower() for k in raw.get("keywords", []) if str(k).strip()]
    kws = list(dict.fromkeys(kws))[:8] or _heuristic_keywords(cand["answer"])

    pts = [str(p).strip() for p in raw.get("ideal_answer_points", []) if str(p).strip()]
    pts = list(dict.fromkeys(pts))[:6] or _heuristic_points(cand["answer"])

    tags = [str(t).strip().lower() for t in raw.get("tags", [])]
    tags = [t for t in dict.fromkeys(tags) if t in VALID_TAGS][:4]
    if not tags:
        tags = list(CATEGORY_DEFAULT_TAGS.get(cat, ["communication"]))

    return {"category": cat, "type": typ, "difficulty": diff,
            "keywords": kws, "ideal_answer_points": pts, "tags": tags}


def _heuristic_keywords(answer: str) -> List[str]:
    out: List[str] = []
    for w in _words(answer):
        if len(w) > 3 and w not in _STOP and w not in out:
            out.append(w)
        if len(out) >= 6:
            break
    return out or ["concept"]


def _heuristic_points(answer: str) -> List[str]:
    # Split the reference answer into sentence/clause atoms.
    parts = re.split(r"(?<=[.!?])\s+|;\s+", answer)
    pts = [p.strip().rstrip(".") for p in parts if len(p.split()) >= 3]
    return pts[:5] or [answer.strip().rstrip(".")]


def heuristic_enrich(cand: dict) -> dict:
    cat = cand["approx_category"]
    return {"category": cat,
            "type": CATEGORY_DEFAULT_TYPE.get(cat, "technical"),
            "difficulty": 3,
            "keywords": _heuristic_keywords(cand["answer"]),
            "ideal_answer_points": _heuristic_points(cand["answer"]),
            "tags": list(CATEGORY_DEFAULT_TAGS.get(cat, ["communication"]))}


def _qhash(question: str) -> str:
    return hashlib.sha1(_norm(question).encode("utf-8")).hexdigest()[:16]


def llm_enrich_one(client, cand: dict) -> Optional[dict]:
    """One structured qwen2.5:7b call; sanitized dict on success, None on failure."""
    prompt = _build_enrich_prompt(cand["question"], cand["answer"], cand["approx_category"])
    for attempt in (1, 2):
        try:
            resp = client.chat(
                model=LLM_MODEL,
                messages=[{"role": "system", "content": ENRICH_SYSTEM},
                          {"role": "user", "content": prompt}],
                format=ENRICH_SCHEMA,
                options={"temperature": 0.0, "num_ctx": 4096, "num_predict": 500},
                keep_alive=300,
            )
            raw = json.loads(resp.message.content)
            return _sanitize_semantic(raw, cand)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("Enrich output invalid (attempt %d): %s", attempt, exc)
            prompt += "\n\nYour previous output was not valid JSON. Return ONLY valid JSON."
        except Exception as exc:
            logger.error("Enrich call failed (attempt %d): %s", attempt, exc)
            break
    return None


def ollama_smoke_ok(client) -> bool:
    try:
        client.chat(model=LLM_MODEL,
                    messages=[{"role": "user", "content": "reply with the word ok"}],
                    options={"temperature": 0.0, "num_predict": 5}, keep_alive=300)
        return True
    except Exception as exc:
        logger.error("Ollama smoke test failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Mechanical field assembly (heuristics) -> full schema-valid record.
# ---------------------------------------------------------------------------
def _rubric_for(typ: str) -> dict:
    if typ == "behavioral":
        dims = [
            {"name": "structure", "weight": 0.3, "criteria": "Clear STAR structure"},
            {"name": "specificity", "weight": 0.4, "criteria": "Concrete, non-generic detail"},
            {"name": "reflection", "weight": 0.3, "criteria": "Ownership and insight"},
        ]
        flags = ["Blames others entirely", "No concrete example or outcome"]
    elif typ == "situational":
        dims = [
            {"name": "reasoning", "weight": 0.5, "criteria": "Sound, structured approach to the scenario"},
            {"name": "tradeoffs", "weight": 0.3, "criteria": "Weighs options and consequences"},
            {"name": "communication", "weight": 0.2, "criteria": "Clear, organized explanation"},
        ]
        flags = ["Ignores the constraints given", "No actionable plan"]
    else:   # technical / conceptual
        dims = [
            {"name": "correctness", "weight": 0.5, "criteria": "Technically accurate; addresses the core concept"},
            {"name": "completeness", "weight": 0.3, "criteria": "Covers the key ideal-answer points"},
            {"name": "clarity", "weight": 0.2, "criteria": "Clear, well-structured explanation"},
        ]
        flags = ["Fundamental misconception", "Off-topic or evasive answer"]
    return {"max_score": 5, "dimensions": dims, "red_flags": flags}


def _seconds_for(typ: str, difficulty: int) -> int:
    if typ in ("behavioral", "situational"):
        return 120
    return 60 + 15 * max(1, min(5, difficulty))     # 75..135


def assemble_record(sem: dict, qid: str, question: str, llm_used: bool) -> dict:
    typ = sem["type"]
    diff = sem["difficulty"]
    star = {"required": True} if typ in ("behavioral", "situational") else None
    return {
        "id": qid, "version": 1, "text": question,
        "category": sem["category"], "type": typ, "difficulty": diff,
        "tags": sem["tags"], "role_fit": ["*"],
        "irt": {"a": 1.0, "b": TIER_TO_B[diff], "c": 0.0,
                "calibration": {"status": "seed", "n_responses": 0,
                                "seed_source": "heuristic+tier2" if llm_used else "heuristic",
                                "last_calibrated": None}},
        "ideal_answer_points": sem["ideal_answer_points"],
        "keywords": sem["keywords"],
        "expected_star": star,
        "scoring_rubric": _rubric_for(typ),
        "follow_up_ids": [], "easier_ids": [], "harder_ids": [],
        "expected_answer_seconds": _seconds_for(typ, diff),
        "source": "dataset-import", "created_at": "2026-09-27",
        "usage_count": 0, "language": "en",
    }


# ---------------------------------------------------------------------------
# Cache + output
# ---------------------------------------------------------------------------
def load_cache(use_cache: bool) -> Dict[str, dict]:
    if use_cache and CACHE_PATH.exists():
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache: Dict[str, dict]) -> None:
    tmp = CACHE_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    tmp.replace(CACHE_PATH)


def assign_ids_and_write(sems: List[Tuple[dict, dict, bool]]) -> dict:
    """sems: list of (candidate, semantic, llm_used). Groups by FINAL category,
    assigns deterministic ids from 500+, writes the generated bank file."""
    by_cat: Dict[str, List[Tuple[dict, dict, bool]]] = {}
    for cand, sem, used in sems:
        by_cat.setdefault(sem["category"], []).append((cand, sem, used))

    questions: List[dict] = []
    for cat in CATEGORIES:
        group = by_cat.get(cat, [])
        group.sort(key=lambda t: _qhash(t[0]["question"]))   # deterministic order
        prefix = CATEGORY_PREFIX[cat]
        for i, (cand, sem, used) in enumerate(group):
            n = ID_START + i
            if n > 999:
                logger.warning("Category %s exceeds 3-digit id space; truncating", cat)
                break
            questions.append(assemble_record(sem, f"{prefix}-{n:03d}", cand["question"], used))

    counts: Dict[str, int] = {}
    for q in questions:
        counts[q["category"]] = counts.get(q["category"], 0) + 1
    out = {
        "schema_version": 1,
        "count": len(questions),
        "category_index": counts,
        "note": ("Auto-generated from the imported Q&A dataset (source=dataset-import). "
                 "Hybrid enrichment: heuristics for mechanical fields + qwen2.5:7b for "
                 "category/type/difficulty/keywords/ideal_answer_points/tags. NOT "
                 "SME-reviewed - expert review recommended before production use. "
                 "Regenerate with scripts/enrich_dataset.py; delete this file to revert."),
        "questions": questions,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Enrich the imported Q&A dataset into bank items.")
    ap.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    ap.add_argument("--cap", type=int, default=40, help="max items per non-security category")
    ap.add_argument("--security-cap", type=int, default=100, help="max tech_security items")
    ap.add_argument("--heuristic-only", action="store_true", help="skip the LLM entirely")
    ap.add_argument("--no-cache", action="store_true", help="ignore the enrichment cache")
    ap.add_argument("--dry-run", action="store_true", help="size the workload, no LLM, no write")
    args = ap.parse_args()

    rows = load_dataset(args.dataset_dir)
    if not rows:
        logger.error("No dataset rows found under %s", args.dataset_dir)
        return 1
    candidates, stats = clean_and_dedup(rows)
    selected = balance(candidates, args.cap, args.security_cap)

    approx_counts: Dict[str, int] = {}
    for c in selected:
        approx_counts[c["approx_category"]] = approx_counts.get(c["approx_category"], 0) + 1
    logger.info("Clean/dedup stats: %s", stats)
    logger.info("Selected %d candidates (approx categories): %s",
                len(selected), dict(sorted(approx_counts.items())))

    if args.dry_run:
        print(json.dumps({"stats": stats, "selected_total": len(selected),
                          "approx_categories": approx_counts}, indent=2))
        return 0

    cache = load_cache(not args.no_cache)
    client = None
    if not args.heuristic_only:
        try:
            import ollama
            client = ollama.Client(host=OLLAMA_HOST)
        except ImportError:
            logger.error("ollama package not importable; falling back to --heuristic-only")
        if client is not None and not ollama_smoke_ok(client):
            logger.error("Ollama not reachable / model missing. Start Ollama with "
                         "%s, or re-run with --heuristic-only.", LLM_MODEL)
            return 2

    sems: List[Tuple[dict, dict, bool]] = []
    total = len(selected)
    llm_hits = cache_hits = fallbacks = 0
    for idx, cand in enumerate(selected, 1):
        h = _qhash(cand["question"])
        sem = cache.get(h) if not args.no_cache else None
        used = True
        if sem is not None:
            cache_hits += 1          # cache only ever holds LLM-derived results
        elif client is not None:
            sem = llm_enrich_one(client, cand)
            if sem is None:
                sem, used = heuristic_enrich(cand), False
                fallbacks += 1
            else:
                llm_hits += 1
                cache[h] = sem
                if llm_hits % 10 == 0:
                    save_cache(cache)
        else:
            sem, used = heuristic_enrich(cand), False
        sems.append((cand, sem, used))
        if idx % 25 == 0 or idx == total:
            logger.info("enriched %d/%d (llm=%d cache=%d fallback=%d)",
                        idx, total, llm_hits, cache_hits, fallbacks)

    if client is not None:
        save_cache(cache)

    out = assign_ids_and_write(sems)
    logger.info("WROTE %s: %d questions, categories=%s",
                OUT_PATH.name, out["count"], out["category_index"])
    print(json.dumps({"written": str(OUT_PATH), "count": out["count"],
                      "category_index": out["category_index"],
                      "llm": llm_hits, "cache": cache_hits, "fallback": fallbacks}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())








