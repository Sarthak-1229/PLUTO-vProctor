"""
Validate data/question_bank.json for PLUTO vProctor.

Checks: JSON well-formedness, draft-07 schema conformance (jsonschema if available,
else a structural fallback), unique + pattern-valid ids, referential integrity of
follow_up/easier/harder links, category counts vs the declared index, difficulty
range, and role_fit slugs against the taxonomy.

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
SCHEMA = DATA / "question_schema.json"
TAXONOMY = DATA / "skill_taxonomy.json"

ID_RE = re.compile(r"^[a-z]+-[0-9]{3}[a-z]?$")


def _load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    errors = []
    warnings = []

    bank = _load(BANK)
    schema = _load(SCHEMA)
    taxonomy = _load(TAXONOMY)

    questions = bank.get("questions", [])
    roles = set(taxonomy.get("roles", {}).keys()) | {"*"}

    # --- schema validation (prefer jsonschema, fall back to a light check) ---
    try:
        import jsonschema
        validator = jsonschema.Draft7Validator(schema)
        for q in questions:
            for err in validator.iter_errors(q):
                loc = "/".join(str(p) for p in err.path)
                errors.append(f"[schema] {q.get('id','?')}::{loc}: {err.message}")
    except ImportError:
        warnings.append("jsonschema not installed - running structural fallback only")
        required = schema.get("required", [])
        for q in questions:
            missing = [k for k in required if k not in q]
            if missing:
                errors.append(f"[struct] {q.get('id','?')}: missing {missing}")

    # --- id uniqueness + pattern ---
    ids = [q.get("id", "") for q in questions]
    seen = set()
    for qid in ids:
        if not ID_RE.match(qid):
            errors.append(f"[id] '{qid}' does not match ^[a-z]+-[0-9]{{3}}[a-z]?$")
        if qid in seen:
            errors.append(f"[id] duplicate id '{qid}'")
        seen.add(qid)
    idset = set(ids)

    # --- referential integrity of links ---
    for q in questions:
        for field in ("follow_up_ids", "easier_ids", "harder_ids"):
            for ref in q.get(field, []):
                if ref not in idset:
                    errors.append(f"[link] {q['id']}.{field} -> unknown id '{ref}'")

    # --- role_fit slugs exist in taxonomy ---
    for q in questions:
        for r in q.get("role_fit", []):
            if r not in roles:
                warnings.append(f"[role] {q['id']} role_fit '{r}' not in taxonomy")

    # --- difficulty range (defensive; schema also checks) ---
    for q in questions:
        d = q.get("difficulty")
        if not isinstance(d, int) or not (1 <= d <= 5):
            errors.append(f"[difficulty] {q.get('id','?')} difficulty={d} out of 1..5")

    # --- category counts vs declared index + count ---
    counts = {}
    for q in questions:
        counts[q.get("category", "?")] = counts.get(q.get("category", "?"), 0) + 1
    declared = bank.get("category_index", {})
    for cat, n in declared.items():
        if counts.get(cat, 0) != n:
            errors.append(f"[count] category '{cat}': declared {n}, found {counts.get(cat,0)}")
    for cat in counts:
        if cat not in declared:
            warnings.append(f"[count] category '{cat}' present but not in category_index")
    if bank.get("count") != len(questions):
        errors.append(f"[count] declared count {bank.get('count')} != actual {len(questions)}")

    # --- report ---
    print(f"Validated {len(questions)} questions from {BANK.name}")
    print(f"  categories: {counts}")
    for w in warnings:
        print(f"  WARN  {w}")
    if errors:
        print(f"\n{len(errors)} ERROR(S):")
        for e in errors:
            print(f"  FAIL  {e}")
        return 1
    print("\nOK - question bank is valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
