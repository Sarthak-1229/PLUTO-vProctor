"""Ingest, clean, deduplicate, and audit interview datasets from datasets/data*/.

Implements Section 2B.1 of docs/spec/2B-dataset.md.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.app.algorithms.minhash import jaccard_from_signatures, minhash_signature

DATASETS_DIR = ROOT_DIR / "datasets"
PROCESSED_DIR = ROOT_DIR / "backend" / "app" / "data" / "processed"
REPORT_FILE = ROOT_DIR / "docs" / "DATASET_REPORT.md"
OUTPUT_FILE = PROCESSED_DIR / "qa_clean.jsonl"

QUESTION_ALIASES = ["question", "prompt", "instruction", "q", "input"]
ANSWER_ALIASES = ["answer", "response", "output", "a", "completion"]

SPLIT_PRIORITY = {"test": 3, "val": 2, "train": 1}


def normalize_text(text: str) -> str:
    """Normalize unicode quotes, dashes, whitespace, and case."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    # Replace stylized quotes and dashes
    text = re.sub(r"[‘’‚‛]", "'", text)
    text = re.sub(r"[“”„‟]", '"', text)
    text = re.sub(r"[–—―]", "-", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_for_dedup(text: str) -> str:
    """Lowercase and strip non-alphanumeric chars for exact duplicate check."""
    text = normalize_text(text).lower()
    return re.sub(r"[^a-z0-9\s]", "", text).strip()


def compute_question_id(norm_q: str) -> str:
    """Generate a stable, deterministic ID from the normalized question text."""
    h = hashlib.sha256(norm_q.encode("utf-8")).hexdigest()[:12]
    return f"q_{h}"


def load_file_rows(path: Path) -> Tuple[List[Dict[str, Any]], str]:
    """Defensively load a dataset file (JSONL, JSON array, or wrapped dict)."""
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return [], "empty"

    # Try JSONL
    if "\n" in text:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        try:
            rows = [json.loads(line) for line in lines]
            return rows, "JSONL"
        except json.JSONDecodeError:
            pass

    # Try JSON array or object
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data, "JSON Array"
        if isinstance(data, dict):
            for k in ["data", "rows", "items", "questions"]:
                if k in data and isinstance(data[k], list):
                    return data[k], f"JSON Object ({k})"
            return [data], "JSON Object (Single)"
    except json.JSONDecodeError as e:
        print(f"Warning: Failed to parse {path}: {e}")
        return [], "invalid"

    return [], "unknown"


def extract_fields(row: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    """Extract question, answer, and any extra metadata fields."""
    q = None
    a = None
    extras = {}

    for k, v in row.items():
        k_lower = k.lower().strip()
        if q is None and k_lower in QUESTION_ALIASES and isinstance(v, str):
            q = v
        elif a is None and k_lower in ANSWER_ALIASES and isinstance(v, str):
            a = v
        else:
            extras[k] = v

    return q, a, extras


def ingest():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)

    print("=== Scanning datasets/ directory ===")
    files = sorted(DATASETS_DIR.rglob("*"))
    dataset_files = [f for f in files if f.is_file() and f.suffix in [".json", ".jsonl"]]

    raw_stats = []
    all_records: List[Dict[str, Any]] = []

    for fpath in dataset_files:
        rel_path = fpath.relative_to(ROOT_DIR)
        source_folder = fpath.parent.name  # 'data' or 'data1'
        split_name = fpath.stem.lower()    # 'train', 'val', 'test'
        if split_name not in SPLIT_PRIORITY:
            # Try to infer split
            for sp in ["train", "val", "test"]:
                if sp in split_name:
                    split_name = sp
                    break
            else:
                split_name = "train"

        rows, fmt = load_file_rows(fpath)
        keys_found = set()
        empty_q = 0
        empty_a = 0
        valid_rows = 0

        for r in rows:
            keys_found.update(r.keys())
            q, a, extras = extract_fields(r)
            if not q or not q.strip():
                empty_q += 1
                continue
            if not a or not a.strip():
                empty_a += 1
                continue

            q_norm = normalize_text(q)
            a_norm = normalize_text(a)

            record = {
                "question": q_norm,
                "answer": a_norm,
                "norm_q": normalize_for_dedup(q_norm),
                "source_folder": source_folder,
                "split": split_name,
                "original_file": str(rel_path).replace("\\", "/"),
                "extras": extras,
            }
            all_records.append(record)
            valid_rows += 1

        raw_stats.append({
            "file": str(rel_path).replace("\\", "/"),
            "format": fmt,
            "total_rows": len(rows),
            "valid_rows": valid_rows,
            "empty_q": empty_q,
            "empty_a": empty_a,
            "keys": sorted(list(keys_found)),
        })
        print(f"Loaded {rel_path}: {valid_rows}/{len(rows)} valid records ({fmt})")

    total_loaded = len(all_records)
    print(f"\nTotal raw valid records loaded: {total_loaded}")

    # Deduplication & Leakage Prevention (test > val > train)
    # Sort all records by split priority descending so higher priority splits claim duplicates first
    all_records.sort(key=lambda r: SPLIT_PRIORITY.get(r["split"], 0), reverse=True)

    exact_seen: Dict[str, Dict[str, Any]] = {}
    exact_duplicates_removed = 0
    cross_split_leakage_prevented = 0

    surviving_exact: List[Dict[str, Any]] = []

    for r in all_records:
        norm_q = r["norm_q"]
        if norm_q in exact_seen:
            existing = exact_seen[norm_q]
            if existing["split"] != r["split"]:
                cross_split_leakage_prevented += 1
            else:
                exact_duplicates_removed += 1
            continue
        exact_seen[norm_q] = r
        surviving_exact.append(r)

    print(f"After exact dedup: {len(surviving_exact)} unique questions remaining.")
    print(f"  - Exact duplicates dropped (e.g. data1 mirror): {exact_duplicates_removed}")
    print(f"  - Cross-split duplicate leakage prevented: {cross_split_leakage_prevented}")

    # Near-duplicate detection with MinHash (Jaccard >= 0.85 on 3-shingles)
    signatures = []
    final_records: List[Dict[str, Any]] = []
    near_duplicates_removed = 0

    for r in surviving_exact:
        sig = minhash_signature(r["norm_q"])

        # Check against already accepted records
        is_near_dup = False
        for existing_sig in signatures:
            if jaccard_from_signatures(sig, existing_sig) >= 0.88:
                is_near_dup = True
                break

        if is_near_dup:
            near_duplicates_removed += 1
            continue

        signatures.append(sig)
        qid = compute_question_id(r["norm_q"])
        r["id"] = qid
        final_records.append(r)

    print(f"After MinHash near-duplicate filter: {len(final_records)} surviving records.")
    print(f"  - Near-duplicates dropped: {near_duplicates_removed}")

    # Split breakdown
    split_counts = Counter(r["split"] for r in final_records)
    print("\nSurviving split counts:")
    for sp in ["train", "val", "test"]:
        print(f"  - {sp}: {split_counts[sp]}")

    # Output to qa_clean.jsonl
    with open(OUTPUT_FILE, "w", encoding="utf-8") as out_f:
        for r in final_records:
            clean_obj = {
                "id": r["id"],
                "question": r["question"],
                "answer": r["answer"],
                "split": r["split"],
                "source_folder": r["source_folder"],
            }
            if r["extras"]:
                clean_obj["extras"] = r["extras"]
            out_f.write(json.dumps(clean_obj, ensure_ascii=False) + "\n")

    print(f"\nWritten {len(final_records)} clean records to {OUTPUT_FILE}")

    # Length distributions and opening stats
    q_word_lens = [len(r["question"].split()) for r in final_records]
    a_word_lens = [len(r["answer"].split()) for r in final_records]

    openings = Counter()
    for r in final_records:
        words = r["question"].split()
        if len(words) >= 2:
            openings[f"{words[0]} {words[1]}".lower()] += 1
        elif words:
            openings[words[0].lower()] += 1

    # Write DATASET_REPORT.md
    with open(REPORT_FILE, "w", encoding="utf-8") as rep_f:
        rep_f.write("# PLUTO vProctor — Dataset Ingestion and Schema Audit Report\n\n")
        rep_f.write("Generated by `scripts/ingest_datasets.py` per Section 2B.1 of `docs/spec/2B-dataset.md`.\n\n")

        rep_f.write("## 1. Raw Files & Schema Audit\n\n")
        rep_f.write("| File Path | Format | Total Rows | Valid Rows | Empty Q | Empty A | Detected Keys |\n")
        rep_f.write("|---|---|---|---|---|---|---|\n")
        for s in raw_stats:
            rep_f.write(f"| `{s['file']}` | {s['format']} | {s['total_rows']} | {s['valid_rows']} | {s['empty_q']} | {s['empty_a']} | `{', '.join(s['keys'])}` |\n")
        rep_f.write("\n")

        rep_f.write("## 2. Ingestion & Deduplication Pipeline\n\n")
        rep_f.write(f"- **Total raw entries ingested across all files:** {total_loaded}\n")
        rep_f.write(f"- **Exact duplicates removed (including `data1/` mirrors):** {exact_duplicates_removed}\n")
        rep_f.write(f"- **Cross-split leakage dropped (strictly prioritizing `test > val > train`):** {cross_split_leakage_prevented}\n")
        rep_f.write(f"- **Near-duplicates removed via MinHash 3-shingle similarity:** {near_duplicates_removed}\n")
        rep_f.write(f"- **Final surviving clean questions:** **{len(final_records)}**\n\n")

        rep_f.write("### Split Distribution of Clean Dataset\n\n")
        rep_f.write("| Split | Count | Percentage |\n")
        rep_f.write("|---|---|---|\n")
        for sp in ["train", "val", "test"]:
            cnt = split_counts[sp]
            pct = (cnt / len(final_records)) * 100
            rep_f.write(f"| **`{sp}`** | {cnt} | {pct:.1f}% |\n")
        rep_f.write(f"| **Total** | {len(final_records)} | 100.0% |\n\n")

        rep_f.write("## 3. Length & Structural Statistics\n\n")
        rep_f.write("| Metric | Question Length (words) | Answer Length (words) |\n")
        rep_f.write("|---|---|---|\n")
        rep_f.write(f"| Minimum | {min(q_word_lens)} | {min(a_word_lens)} |\n")
        rep_f.write(f"| Mean | {sum(q_word_lens)/len(q_word_lens):.1f} | {sum(a_word_lens)/len(a_word_lens):.1f} |\n")
        rep_f.write(f"| Maximum | {max(q_word_lens)} | {max(a_word_lens)} |\n\n")

        rep_f.write("## 4. Top 15 Question Openings\n\n")
        rep_f.write("| Opening Bigram | Frequency | Example Question |\n")
        rep_f.write("|---|---|---|\n")
        for op, freq in openings.most_common(15):
            sample = next((r["question"] for r in final_records if r["question"].lower().startswith(op)), "")
            rep_f.write(f"| `{op}` | {freq} | *\"{sample}\"* |\n")
        rep_f.write("\n")

        rep_f.write("## 5. Sample Ingested Records\n\n")
        rep_f.write("```json\n")
        for r in final_records[:3]:
            sample_obj = {"id": r["id"], "split": r["split"], "question": r["question"], "answer": r["answer"]}
            rep_f.write(json.dumps(sample_obj, indent=2) + "\n")
        rep_f.write("```\n")

    print(f"Wrote audit report to {REPORT_FILE}")


if __name__ == "__main__":
    ingest()
