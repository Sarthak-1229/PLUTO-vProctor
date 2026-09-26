"""
Tests for the PLUTO vProctor adaptive engine + Tier-1 evaluator (Part 3).

Covers: Elo/target-difficulty math, the confidence-building FSM transitions
(driven by CONTENT score S only), Tier-1 scoring (good/weak/non-answer), and a
full serve->grade->adapt loop over a real résumé-selected pool. CPU-only, no
network. Exit 0 = pass, 1 = fail.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.interview.adaptive import (
    get_adaptive_engine, expected, target_b, topic_of,
    P_STAR,
)
from core.interview.session_store import (
    InterviewSession, get_session_store,
    FSM_MEASURE, FSM_REBUILD, FSM_ESCALATE, FSM_SWITCH,
)
from core.interview.eval_tier1 import get_tier1_evaluator
from core.interview.question_bank import get_question_bank
from core.interview.resume_parser import get_resume_parser

_fail = [0]


def check(name, cond, detail=""):
    mark = "PASS" if cond else "FAIL"
    if not cond:
        _fail[0] += 1
    print(f"  [{mark}] {name}{(' - ' + detail) if detail else ''}")
    return cond


def dummy_q(qid="tst-001", b=1300):
    return {"id": qid, "category": "tech_backend", "irt": {"b": b},
            "keywords": [], "ideal_answer_points": []}


def test_elo_math():
    print("Elo / target-difficulty math")
    check("E==0.5 when b==R", abs(expected(1250, 1250) - 0.5) < 1e-9)
    check("E>0.5 when able > item", expected(1450, 1250) > 0.5)
    # higher p* => easier => lower target b
    b_easy = target_b(1250, P_STAR[FSM_REBUILD])    # 0.80
    b_mid = target_b(1250, P_STAR[FSM_MEASURE])     # 0.55
    b_hard = target_b(1250, P_STAR[FSM_ESCALATE])   # 0.40
    check("b(REBUILD) < b(MEASURE) < b(ESCALATE)", b_easy < b_mid < b_hard,
          f"{b_easy:.0f} < {b_mid:.0f} < {b_hard:.0f}")


def test_fsm():
    print("Confidence-building FSM (CONTENT-only)")
    eng = get_adaptive_engine()
    s = InterviewSession(session_id="fsm", ability=1250.0)

    def step(S):
        return eng.record_answer(s, dummy_q(), S)["phase_after"]

    check("1st high stays MEASURE", step(0.9) == FSM_MEASURE)
    check("2nd high -> ESCALATE", step(0.9) == FSM_ESCALATE)
    r_peak = s.ability
    check("ability rose after highs", r_peak > 1250.0, f"{r_peak:.0f}")
    check("mid answer drops ESCALATE -> MEASURE", step(0.5) == FSM_MEASURE)
    check("1st low stays MEASURE", step(0.3) == FSM_MEASURE)
    check("2nd low -> REBUILD", step(0.3) == FSM_REBUILD)
    check("3rd low stays REBUILD", step(0.3) == FSM_REBUILD)
    check("4th low -> SWITCH", step(0.3) == FSM_SWITCH)
    check("recovery from SWITCH -> MEASURE", step(0.9) == FSM_MEASURE)
    check("ability fell below peak after lows", s.ability < r_peak, f"{s.ability:.0f}")


def test_tier1():
    print("Tier-1 evaluator")
    ev = get_tier1_evaluator()
    qb = get_question_bank()
    q = qb.get("cs-001") or qb.all_questions()[0]
    # Build a 'good' answer from the question's own keywords + ideal points.
    good = " ".join(q.get("keywords", [])) + ". " + \
           " ".join(q.get("ideal_answer_points", []))
    r_good = ev.score(q, good)
    r_none = ev.score(q, "I don't know, sorry.")
    r_weak = ev.score(q, "It is a thing that does stuff I guess maybe.")
    print(f"   good S={r_good.content_score} weak S={r_weak.content_score} none non_answer={r_none.is_non_answer}")
    check("good answer scores high", r_good.content_score >= 0.6, str(r_good.content_score))
    check("non-answer flagged", r_none.is_non_answer and r_none.content_score < 0.1)
    check("good > weak", r_good.content_score > r_weak.content_score)


def test_full_loop():
    print("Full serve -> grade -> adapt loop over a résumé-selected pool")
    parser = get_resume_parser()
    qb = get_question_bank()
    eng = get_adaptive_engine()
    store = get_session_store()

    prof = parser.parse_text(
        "Backend engineer, 4 years, Python and SQL, REST APIs, Docker.")
    pool = qb.select_for_resume(prof.skills, prof.inferred_role, limit=10)
    sess = store.create(target_role=prof.inferred_role, seniority=prof.inferred_seniority,
                        resume_tags=prof.skills, pool_ids=[q["id"] for q in pool])

    schedule = [0.8, 0.85, 0.3, 0.3, 0.3, 0.9, 0.55, 0.7, 0.2, 0.6]
    served, i = 0, 0
    seen_ids = set()
    while True:
        q = eng.next_question(sess, qb)
        if q is None:
            break
        sel = q.get("_selection", {})
        if not (900.0 <= sel.get("b_target", 1300) <= 1700.0):
            check("b_target within [900,1700]", False, str(sel.get("b_target")))
        if q["id"] in seen_ids:
            check("no repeat served", False, q["id"])
        seen_ids.add(q["id"])
        S = schedule[i % len(schedule)]
        eng.record_answer(sess, q, S)
        served += 1
        i += 1

    print(f"   served {served}, answers {len(sess.answers)}, "
          f"ability {sess.ability:.0f}, topics {sess.topic_ability}")
    check("served entire pool", served == len(pool), f"{served}/{len(pool)}")
    check("all served unique", len(seen_ids) == served)
    check("answers recorded == served", len(sess.answers) == served)
    check("per-topic ability tracked", len(sess.topic_ability) >= 1)


def main():
    test_elo_math()
    test_fsm()
    test_tier1()
    test_full_loop()
    if _fail[0]:
        print(f"\n{_fail[0]} FAILURE(S).")
        return 1
    print("\nOK - adaptive engine + Tier-1 evaluator valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
