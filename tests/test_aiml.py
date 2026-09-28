"""
Tests for the PLUTO vProctor classical-AIML layer (MDM AIML requirement 6).

Hermetic, CPU-only, no network / no Ollama. Verifies that every named-algorithm
artifact loads and predicts, that the search/CSP selectors honor the engine's
invariants (in-pool picks, REBUILD -> strictly-easier same-domain, ESCALATE ->
harder, CSP quotas/size/uniqueness/tier-spread), that the probability ability
band is well-formed, that the report's calibration block leaks no answer-key and
no verdict words, and that every AIML flag OFF -> graceful None fallback.

Requires the artifacts under data/models/ (run experiments/train_all.py first).
Exit 0 = pass, 1 = fail (CI-friendly).
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from core.interview.question_bank import DEFAULT_QUOTAS, get_question_bank

_fail = [0]


def check(name, cond, extra=""):
    tag = "PASS" if cond else "FAIL"
    if not cond:
        _fail[0] += 1
    print(f"  [{tag}] {name}" + (f" - {extra}" if extra else ""))
    return cond


def _bval(bank, qid) -> float:
    return float((bank.get(qid).get("irt") or {}).get("b", 1300))


# PLACEHOLDER_TESTS
def test_grader():
    print("\n[aiml] grader loads + predicts")
    from core.aiml.grader_ml import get_ml_grader
    g = get_ml_grader()
    if not check("grader artifact loads", g is not None):
        return
    bank = get_question_bank()
    q = next((x for x in bank.all_questions() if x.get("ideal_answer_points")), None)
    if not check("found a question with ideal points", q is not None):
        return
    good = " ".join(str(p) for p in q["ideal_answer_points"])
    s_good = g.score(q, good)
    s_bad = g.score(q, "banana umbrella nonsense unrelated words")
    check("score in [0,1]", 0.0 <= s_good <= 1.0 and 0.0 <= s_bad <= 1.0,
          f"{s_good:.3f} / {s_bad:.3f}")
    check("ideal-points answer scores >= off-topic", s_good >= s_bad,
          f"{s_good:.3f} vs {s_bad:.3f}")
    check("band is a valid label", g.band(q, good) in ("correct", "partial", "incorrect"))


def test_topics():
    print("\n[aiml] topics loads + structure queries")
    from core.aiml.topics import get_topic_model
    tm = get_topic_model()
    if not check("topics artifact loads", tm is not None):
        return
    bank = get_question_bank()
    qid = bank.all_questions()[0]["id"]
    check("cluster_of returns int", isinstance(tm.cluster_of(qid), int))
    cands = [q["id"] for q in bank.all_questions()][:60]
    nb = tm.same_domain_neighbors(qid, cands)
    check("same_domain_neighbors returns list", isinstance(nb, list))
    dom = tm.category.get(qid)
    check("all neighbors share the domain (category)",
          all(tm.category.get(c) == dom for c in nb), dom or "?")


def test_difficulty_and_bands():
    print("\n[aiml] difficulty regressor + probability ability band")
    from core.aiml.difficulty_reg import ability_confidence, get_difficulty_model
    m = get_difficulty_model()
    if check("difficulty artifact loads", m is not None):
        b = m.predict_b(get_question_bank().all_questions()[0])
        check("predict_b returns a plausible Elo float",
              isinstance(b, float) and 500 < b < 2500, f"{b:.1f}")
    ac0 = ability_confidence(1300, [])
    check("ability band n=0 -> note, no band",
          ac0.get("n_items") == 0 and "note" in ac0)

    class _A:
        b_question = 1300.0

    ac = ability_confidence(1300.0, [_A(), _A(), _A()])
    check("ability band n=3 -> finite SE", ac.get("standard_error_elo") is not None)
    band = ac.get("band_80pct_elo")
    check("ability band brackets the estimate",
          bool(band) and band[0] < 1300 < band[1], str(band))


def test_search():
    print("\n[aiml] search selection (A*/BFS/DLS/IDS over the question graph)")
    from core.aiml.selection_search import _bucket, get_selection_search
    ss = get_selection_search()
    if not check("search selector on (flag)", ss is not None):
        return
    bank = get_question_bank()
    tech = [q["id"] for q in bank.all_questions()
            if q.get("category", "").startswith("tech_")]
    tech = sorted(tech, key=lambda i: _bval(bank, i))[:40]
    tech = sorted(tech, key=lambda i: _bval(bank, i))
    easiest, hardest, mid = tech[0], tech[-1], tech[len(tech) // 2]

    # MEASURE: A* to a node within the target band; pick must be in the pool.
    cands = [c for c in tech if c != mid]
    qid, tr = ss.select(bank, cands, b_target=1300, phase="measure", anchor_id=mid)
    check("measure pick in pool", qid in cands, str(qid))

    # REBUILD from the hardest item -> strictly EASIER, same coarse domain.
    cands_r = [c for c in tech if c != hardest]
    ab = _bval(bank, hardest)
    qid_r, tr_r = ss.select(bank, cands_r, b_target=ab - 150, phase="rebuild",
                            anchor_id=hardest)
    check("rebuild pick in pool", qid_r in cands_r, str(qid_r))
    check("rebuild pick is strictly easier", _bval(bank, qid_r) < ab,
          f"{_bval(bank, qid_r)} vs {ab}")
    check("rebuild pick same coarse domain",
          _bucket(bank.get(qid_r)["category"]) == _bucket(bank.get(hardest)["category"]))

    # ESCALATE from the easiest item -> strictly HARDER.
    cands_e = [c for c in tech if c != easiest]
    ae = _bval(bank, easiest)
    qid_e, tr_e = ss.select(bank, cands_e, b_target=ae + 150, phase="escalate",
                            anchor_id=easiest)
    check("escalate pick in pool", qid_e in cands_e, str(qid_e))
    check("escalate pick is harder", _bval(bank, qid_e) > ae,
          f"{_bval(bank, qid_e)} vs {ae}")


def test_csp():
    print("\n[aiml] CSP pool assembly (backtracking + forward-check + LS + GA)")
    from core.aiml.selection_csp import get_csp_selector
    sel = get_csp_selector()
    if not check("csp selector on (flag)", sel is not None):
        return
    bank = get_question_bank()
    res = sel.select(bank.all_questions(), target_role="backend_engineer",
                     resume_tags=["python", "sql", "docker", "aws"],
                     limit=15, quotas=DEFAULT_QUOTAS)
    if not check("csp returns a feasible pool", res is not None):
        return
    ids, trace = res
    check("csp pool size == limit", len(ids) == 15, str(len(ids)))
    check("csp pool has no duplicates", len(set(ids)) == len(ids))
    cats = Counter(bank.get(i)["category"] for i in ids)
    check("csp meets category quotas",
          all(cats.get(c, 0) >= n for c, n in DEFAULT_QUOTAS.items()), str(dict(cats)))
    check("csp pool spans >= 3 difficulty tiers", len(trace["tiers"]) >= 3,
          str(trace["tiers"]))


def test_calibration_report():
    print("\n[aiml] report calibration block: no answer-key leak, no verdicts")
    from core.interview.adaptive import get_adaptive_engine
    from core.interview.eval_tier1 import get_tier1_evaluator
    from core.interview.report import get_report_builder
    from core.interview.session_store import get_session_store
    bank = get_question_bank()
    pool = bank.select_for_resume(["python", "sql"], target_role="backend", limit=8)
    store = get_session_store()
    s = store.create(target_role="backend", seniority="mid",
                     resume_tags=["python", "sql"], pool_ids=[q["id"] for q in pool],
                     consent={"audio": True, "store_transcript": True})
    eng = get_adaptive_engine()
    t1 = get_tier1_evaluator()
    for _ in range(3):
        q = eng.next_question(s, bank)
        if q is None:
            break
        sc = t1.score(q, "indexing and caching to scale reads").content_score
        eng.record_answer(s, q, sc, content_source="tier1",
                          transcript="indexing and caching to scale reads")
    rep = get_report_builder().build(s, bank)
    cal = rep.get("calibration")
    if not check("calibration block present when flag on", cal is not None):
        return
    blob = json.dumps(cal)
    check("calibration leaks no answer-key fields",
          not any(k in blob for k in ("ideal_answer_points", "scoring_rubric",
                                      "red_flags", "keywords")))
    forbidden = ["nervous", "confidence", "confident", "emotion", "honest",
                 "hireab", "pass/fail", "deception", "bluff"]
    hits = [w for w in forbidden if w in blob.lower()]
    check("calibration carries no verdict words", not hits, str(hits))


def test_flags_off():
    print("\n[aiml] every AIML flag OFF -> graceful None fallback")
    keys = ("AIML_GRADER_ENABLED", "AIML_TOPICS_ENABLED", "AIML_SEARCH_ENABLED",
            "AIML_CSP_ENABLED", "AIML_CALIBRATION_ENABLED")
    saved = {k: getattr(config, k, True) for k in keys}
    try:
        for k in keys:
            setattr(config, k, False)
        from core.aiml.difficulty_reg import get_difficulty_model
        from core.aiml.grader_ml import get_ml_grader
        from core.aiml.selection_csp import get_csp_selector
        from core.aiml.selection_search import get_selection_search
        from core.aiml.topics import get_topic_model
        check("grader off -> None", get_ml_grader() is None)
        check("topics off -> None", get_topic_model() is None)
        check("search off -> None", get_selection_search() is None)
        check("csp off -> None", get_csp_selector() is None)
        check("difficulty off -> None", get_difficulty_model() is None)
    finally:
        for k, v in saved.items():
            setattr(config, k, v)


def main():
    test_grader()
    test_topics()
    test_difficulty_and_bands()
    test_search()
    test_csp()
    test_calibration_report()
    test_flags_off()
    if _fail[0]:
        print(f"\n{_fail[0]} FAILURE(S).")
        return 1
    print("\nOK - classical-AIML layer valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
