"""
Validate the PLUTO vProctor question bank(s).

Covers data/question_bank.json (curated) AND, when present,
data/question_bank_generated.json (auto-enriched from the imported dataset).

Checks: JSON well-formedness, draft-07 schema conformance (jsonschema if available,
else a structural fallback), unique + pattern-valid ids (GLOBAL across both files),
referential integrity of follow_up/easier/harder links against the merged id set,
per-file category counts vs the declared index + count, difficulty range, and
role_fit slugs against the taxonomy.

Run:  python tests/validate_bank.py
Exit code 0 = valid, 1 = problems found (suitable for CI).
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
BANK = DATA / "question_bank.json"
GENERATED = DATA / "question_bank_generated.json"
SCHEMA = DATA / "question_schema.json"
TAXONOMY = DATA / "skill_taxonomy.json"

ID_RE = re.compile(r"^[a-z]+-[0-9]{3}[a-z]?$")


def _load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_schema(questions, schema, errors, warnings, label):
    try:
        import jsonschema
        validator = jsonschema.Draft7Validator(schema)
        for q in questions:
            for err in validator.iter_errors(q):
                loc = "/".join(str(p) for p in err.path)
                errors.append(f"[schema:{label}] {q.get('id','?')}::{loc}: {err.message}")
    except ImportError:
        warnings.append("jsonschema not installed - running structural fallback only")
        required = schema.get("required", [])
        for q in questions:
            missing = [k for k in required if k not in q]
            if missing:
                errors.append(f"[struct:{label}] {q.get('id','?')}: missing {missing}")


def check_counts(bank, questions, errors, warnings, label):
    counts = {}
    for q in questions:
        counts[q.get("category", "?")] = counts.get(q.get("category", "?"), 0) + 1
    declared = bank.get("category_index", {})
    for cat, n in declared.items():
        if counts.get(cat, 0) != n:
            errors.append(f"[count:{label}] category '{cat}': declared {n}, found {counts.get(cat,0)}")
    for cat in counts:
        if cat not in declared:
            warnings.append(f"[count:{label}] category '{cat}' present but not in category_index")
    if bank.get("count") != len(questions):
        errors.append(f"[count:{label}] declared count {bank.get('count')} != actual {len(questions)}")
    return counts


def main():
    errors = []
    warnings = []

    schema = _load(SCHEMA)
    taxonomy = _load(TAXONOMY)
    roles = set(taxonomy.get("roles", {}).keys()) | {"*"}

    files = [("curated", BANK, _load(BANK))]
    if GENERATED.exists():
        files.append(("generated", GENERATED, _load(GENERATED)))

    all_questions = []
    per_file_counts = {}
    for label, path, bank in files:
        qs = bank.get("questions", [])
        all_questions.extend(qs)
        validate_schema(qs, schema, errors, warnings, label)
        per_file_counts[label] = check_counts(bank, qs, errors, warnings, label)

    # --- id uniqueness + pattern (GLOBAL across both files) ---
    seen = set()
    for q in all_questions:
        qid = q.get("id", "")
        if not ID_RE.match(qid):
            errors.append(f"[id] '{qid}' does not match ^[a-z]+-[0-9]{{3}}[a-z]?$")
        if qid in seen:
            errors.append(f"[id] duplicate id '{qid}' (across curated + generated)")
        seen.add(qid)
    idset = set(q.get("id", "") for q in all_questions)

    # --- referential integrity of links (against the merged id set) ---
    for q in all_questions:
        for field in ("follow_up_ids", "easier_ids", "harder_ids"):
            for ref in q.get(field, []):
                if ref not in idset:
                    errors.append(f"[link] {q['id']}.{field} -> unknown id '{ref}'")

    # --- role_fit slugs exist in taxonomy ---
    for q in all_questions:
        for r in q.get("role_fit", []):
            if r not in roles:
                warnings.append(f"[role] {q['id']} role_fit '{r}' not in taxonomy")

    # --- difficulty range (defensive; schema also checks) ---
    for q in all_questions:
        d = q.get("difficulty")
        if not isinstance(d, int) or not (1 <= d <= 5):
            errors.append(f"[difficulty] {q.get('id','?')} difficulty={d} out of 1..5")

    # --- report ---
    print(f"Validated {len(all_questions)} questions across {len(files)} file(s)")
    for label, counts in per_file_counts.items():
        print(f"  {label}: {sum(counts.values())} questions {counts}")
    for w in warnings:
        print(f"  WARN  {w}")
    if errors:
        print(f"\n{len(errors)} ERROR(S):")
        for e in errors:
            print(f"  FAIL  {e}")
        return 1
    print("\nOK - question bank(s) valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
