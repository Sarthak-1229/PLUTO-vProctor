"""
Tests for PLUTO vProctor Part 5: delivery fusion + report builder (+ PDF).

Covers:
  * DeliveryAnalyzer.describe_speech / describe_body produce DESCRIPTIVE strings
    (numbers, no verdict words), and summarize_session aggregates correctly.
  * ReportBuilder.build assembles competence + content + delivery + content-only
    recommendations, always carries the no-verdict disclaimer, and NEVER emits
    forbidden verdict language (emotion / nervous / confidence / hireability / etc.).
  * to_pdf returns real PDF bytes and save_pdf writes a file under a temp dir.

CPU-only, no network, no Ollama. Exit 0 = pass, 1 = fail (CI-friendly).
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.interview.delivery import get_delivery_analyzer
from core.interview.report import get_report_builder, REPORT_DISCLAIMER
from core.interview.question_bank import get_question_bank
from core.interview.session_store import get_session_store
from core.interview.adaptive import get_adaptive_engine
from core.interview.eval_tier1 import get_tier1_evaluator

# Words the report/delivery layer must NEVER use as a judgment.
FORBIDDEN = ["nervous", "confidence", "confident", "emotion", "honest",
             "hireable", "hireability", "pass/fail", "pass or fail",
             "interview-ready", "interview ready", "deception", "bluff"]

_fail = [0]


def check(name, cond, extra=""):
    tag = "PASS" if cond else "FAIL"
    if not cond:
        _fail[0] += 1
    print(f"  [{tag}] {name}" + (f" - {extra}" if extra else ""))
    return cond


def _no_forbidden(text):
    low = text.lower()
    hits = [w for w in FORBIDDEN if w in low]
    return (not hits), hits

def test_delivery_describe():
    print("\n[delivery] single-answer descriptions")
    an = get_delivery_analyzer()
    speech = {"words_per_minute": 138, "word_count": 92, "filler_count": 5,
              "filler_rate_per_min": 4.2, "long_pause_count": 2}
    body = {"face_present_ratio": 0.93, "centered_ratio": 0.81, "mean_motion": 0.021}
    sp_lines = an.describe_speech(speech)
    bd_lines = an.describe_body(body)
    check("speech description non-empty", len(sp_lines) >= 3)
    check("body description non-empty", len(bd_lines) >= 3)
    joined = " ".join(sp_lines + bd_lines)
    ok, hits = _no_forbidden(joined)
    check("delivery lines carry no verdict words", ok, str(hits))
    check("empty inputs yield no lines", an.describe_speech({}) == [] and an.describe_body({}) == [])


def test_delivery_summarize():
    print("\n[delivery] session aggregation")
    an = get_delivery_analyzer()
    answers = [
        {"delivery": {"speech": {"words_per_minute": 120, "filler_rate_per_min": 3, "long_pause_count": 1},
                      "body": {"face_present_ratio": 0.9, "centered_ratio": 0.8, "mean_motion": 0.02}}},
        {"delivery": {"speech": {"words_per_minute": 160, "filler_rate_per_min": 5, "long_pause_count": 2},
                      "body": {"face_present_ratio": 1.0, "centered_ratio": 0.9, "mean_motion": 0.04}}},
    ]
    summ = an.summarize_session(answers)
    check("speech answers counted", summ["speech"]["answers_with_speech_signal"] == 2)
    check("mean wpm averaged", summ["speech"]["mean_words_per_minute"] == 140.0,
          str(summ["speech"]["mean_words_per_minute"]))
    check("long pauses summed", summ["speech"]["total_long_pauses"] == 3)
    check("body answers counted", summ["body"]["answers_with_body_signal"] == 2)
    check("mean face ratio averaged", summ["body"]["mean_face_present_ratio"] == 0.95,
          str(summ["body"]["mean_face_present_ratio"]))
    ok, hits = _no_forbidden(summ.get("disclaimer", ""))
    disc = summ.get("disclaimer", "").lower()
    check("delivery disclaimer explicitly disclaims verdicts (negated, not asserted)",
          "descriptive" in disc and ("not a measure" in disc or "never" in disc), disc[:70])


def _seed_session(n=3):
    """Create a session, serve n questions and record graded answers with delivery."""
    bank = get_question_bank()
    pool = bank.select_for_resume(["python", "sql"], target_role="backend", limit=8)
    store = get_session_store()
    session = store.create(target_role="backend", seniority="mid",
                           resume_tags=["python", "sql"], pool_ids=[q["id"] for q in pool],
                           consent={"audio": True, "store_transcript": True})
    engine = get_adaptive_engine()
    t1 = get_tier1_evaluator()
    answers_text = ["I would use indexing and caching to scale the read path.",
                    "um, not sure", "We resolved the conflict by pairing and writing tests."]
    for i in range(n):
        q = engine.next_question(session, bank)
        if q is None:
            break
        txt = answers_text[i % len(answers_text)]
        s = t1.score(q, txt).content_score
        engine.record_answer(session, q, s, content_source="tier1",
                             transcript=txt,
                             delivery={"speech": {"words_per_minute": 130 + i * 5,
                                                  "filler_rate_per_min": 2 + i, "long_pause_count": i},
                                       "body": {"face_present_ratio": 0.9, "centered_ratio": 0.85,
                                                "mean_motion": 0.02}})
    store.save(session)
    return session, bank

def test_report_build():
    print("\n[report] build() structure + no-verdict invariant")
    session, bank = _seed_session(3)
    rep = get_report_builder().build(session, bank)
    check("has session_id", bool(rep.get("session_id")))
    check("disclaimer matches canonical", rep.get("disclaimer") == REPORT_DISCLAIMER)
    comp = rep.get("competence", {})
    for k in ("overall_ability_elo", "topic_ability_elo", "seniority_declared",
              "target_role", "questions_answered", "final_phase"):
        check(f"competence has {k}", k in comp)
    check("content_breakdown populated", len(rep.get("content_breakdown", [])) == session.n_answered,
          f"{len(rep.get('content_breakdown', []))} vs {session.n_answered}")
    check("delivery observations present", "speech" in rep.get("delivery_observations", {}))
    check("recommendations non-empty", len(rep.get("recommendations", [])) >= 1)
    # No answer-key fields must appear in the content breakdown.
    leak = any(("keywords" in c or "ideal_answer_points" in c or "scoring_rubric" in c)
               for c in rep["content_breakdown"])
    check("no answer-key leak in content_breakdown", not leak)
    # No forbidden verdict language in the report BODY. The disclaimer fields
    # legitimately mention these words to DISCLAIM them ("makes no judgment of
    # emotion / confidence / ...") — those are excluded from the scan.
    import json
    scan = dict(rep)
    scan.pop("disclaimer", None)
    do = dict(scan.get("delivery_observations", {}) or {})
    do.pop("disclaimer", None)
    scan["delivery_observations"] = do
    ok, hits = _no_forbidden(json.dumps(scan))
    check("report body (excl. disclaimers) carries no verdict words", ok, str(hits))


def test_report_pdf():
    print("\n[report] to_pdf + save_pdf")
    session, bank = _seed_session(3)
    builder = get_report_builder()
    rep = builder.build(session, bank)
    try:
        pdf = builder.to_pdf(rep)
    except RuntimeError as exc:
        check("fpdf2 available (skip if not)", False, str(exc))
        return
    check("to_pdf returns bytes", isinstance(pdf, (bytes, bytearray)) and len(pdf) > 500)
    check("PDF magic header", bytes(pdf[:5]) == b"%PDF-")
    with tempfile.TemporaryDirectory() as d:
        path = builder.save_pdf(rep, out_dir=d)
        p = Path(path)
        check("save_pdf wrote a file", p.exists() and p.stat().st_size > 500, path)
        check("saved file is a PDF", p.read_bytes()[:5] == b"%PDF-")


def main():
    test_delivery_describe()
    test_delivery_summarize()
    test_report_build()
    test_report_pdf()
    if _fail[0]:
        print(f"\n{_fail[0]} FAILURE(S).")
        return 1
    print("\nOK - delivery + report builder valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
