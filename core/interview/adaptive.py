"""
Adaptive engine for PLUTO vProctor (COMPETENCE axis — the AI core).

Three layers, all driven by the CONTENT score S in [0,1] ONLY (delivery/
confidence never enters here):
  1. Elo ability rating   — R_u per session (+ per-topic, for the report).
  2. Confidence-building FSM — MEASURE / REBUILD / ESCALATE / SWITCH sets the
     target success probability p* for the next item.
  3. Topic scheduler       — picks the next question nearest the target
     difficulty b* within the current topic bucket; SWITCH changes bucket.

Elo (see plan): E = 1/(1+10^((b_q - R_u)/400)); R_u += K·rel·(S - E);
b_q += 8·(E - S); b* = R_u + 400·log10(1/p* - 1).
"""
import logging
import math
import time
from typing import Dict, List, Optional, Tuple

from core.interview.session_store import (
    InterviewSession, AnswerRecord,
    FSM_MEASURE, FSM_REBUILD, FSM_ESCALATE, FSM_SWITCH,
)

logger = logging.getLogger(__name__)

# Elo / update constants
K_EARLY, K_LATE, EARLY_N = 64.0, 24.0, 5
B_STEP = 8.0
B_MIN, B_MAX = 900.0, 1700.0

# Target success probability per FSM phase (higher p* => easier item).
P_STAR = {FSM_MEASURE: 0.55, FSM_REBUILD: 0.80, FSM_ESCALATE: 0.40, FSM_SWITCH: 0.55}

# CONTENT-score thresholds and streak lengths that drive FSM transitions.
HIGH_S, LOW_S, RECOVER_S = 0.70, 0.40, 0.60
STREAK = 2                     # consecutive highs/lows to change phase
REBUILD_TO_SWITCH = 4          # total consecutive lows before giving up on a topic


def expected(R_u: float, b_q: float) -> float:
    return 1.0 / (1.0 + 10 ** ((b_q - R_u) / 400.0))


def target_b(R_u: float, p_star: float) -> float:
    p = min(0.95, max(0.05, p_star))
    return R_u + 400.0 * math.log10((1.0 / p) - 1.0)


def _clamp_b(b: float) -> float:
    return max(B_MIN, min(B_MAX, b))


def topic_of(q: dict) -> str:
    cat = (q or {}).get("category", "")
    if cat == "behavioral":
        return "behavioral"
    if cat == "hr_culture":
        return "hr"
    if cat == "situational":
        return "situational"
    return "technical"


class AdaptiveEngine:
    """Stateless engine; all mutable state lives on the InterviewSession."""

    @staticmethod
    def _update_ability(R_u: float, b_q: float, S: float, n: int,
                        reliability: float = 1.0) -> Tuple[float, float, float]:
        E = expected(R_u, b_q)
        K = K_EARLY if n < EARLY_N else K_LATE
        R_new = R_u + K * reliability * (S - E)
        b_new = _clamp_b(b_q + B_STEP * (E - S))
        return R_new, b_new, E

    def _transition(self, session: InterviewSession, S: float) -> Tuple[str, str]:
        """Update streaks and return (new_phase, human note). CONTENT-only."""
        if S >= HIGH_S:
            session.consecutive_high += 1
            session.consecutive_low = 0
        elif S <= LOW_S:
            session.consecutive_low += 1
            session.consecutive_high = 0
        else:
            session.consecutive_high = 0
            session.consecutive_low = 0

        cur = session.fsm_phase
        hi, lo = session.consecutive_high, session.consecutive_low

        if cur == FSM_MEASURE:
            if hi >= STREAK:
                return FSM_ESCALATE, "sustained strong answers -> escalating difficulty"
            if lo >= STREAK:
                return FSM_REBUILD, "two weak answers -> easing off to rebuild footing"
            return FSM_MEASURE, "probing at current ability"
        if cur == FSM_REBUILD:
            if S >= RECOVER_S:
                return FSM_MEASURE, "recovered -> back to measuring"
            if lo >= REBUILD_TO_SWITCH:
                return FSM_SWITCH, "still struggling -> switching topic"
            return FSM_REBUILD, "still rebuilding with easier items"
        if cur == FSM_ESCALATE:
            if S < RECOVER_S:
                return FSM_MEASURE, "hit the ceiling -> back to measuring"
            return FSM_ESCALATE, "continuing to push difficulty"
        if cur == FSM_SWITCH:
            return FSM_MEASURE, "new topic -> measuring afresh"
        return FSM_MEASURE, "default"

    def next_question(self, session: InterviewSession, bank) -> Optional[dict]:
        """Choose + serve the next question. Appends it to session.asked_ids.

        Returns the question dict (with a `_selection` trace attached) or None
        when the pool is exhausted.
        """
        asked = set(session.asked_ids)
        remaining = [qid for qid in session.pool_ids if qid not in asked]
        if not remaining:
            return None

        phase = session.fsm_phase
        p_star = P_STAR.get(phase, 0.55)
        b_tgt = target_b(session.ability, p_star)

        # Group remaining questions into topic buckets.
        buckets: Dict[str, List[str]] = {}
        for qid in remaining:
            q = bank.get(qid)
            if q:
                buckets.setdefault(topic_of(q), []).append(qid)
        if not buckets:
            return None

        # Pick the topic bucket: keep current unless SWITCHing or it's empty.
        if (phase == FSM_SWITCH or not session.current_topic
                or session.current_topic not in buckets):
            # Prefer a bucket that is NOT the current one, then the largest.
            chosen_topic = sorted(
                buckets,
                key=lambda t: (t == session.current_topic, -len(buckets[t])),
            )[0]
        else:
            chosen_topic = session.current_topic

        q = bank.nearest_by_difficulty(b_tgt, buckets[chosen_topic], exclude_ids=set())
        if q is None:
            return None

        session.current_topic = chosen_topic
        session.asked_ids.append(q["id"])
        q = dict(q)  # shallow copy so we don't mutate the bank's cached object
        q["_selection"] = {
            "phase": phase, "p_star": p_star, "b_target": round(b_tgt, 1),
            "b_question": q.get("irt", {}).get("b"), "topic": chosen_topic,
            "ability": round(session.ability, 1),
        }
        return q

    def record_answer(self, session: InterviewSession, question: dict, S: float,
                      *, reliability: float = 1.0, content_source: str = "tier1",
                      rubric: Optional[dict] = None,
                      delivery: Optional[dict] = None,
                      transcript: str = "") -> dict:
        """Fold one graded answer into the session state. S is the CONTENT score.

        Returns a trace of the ability/phase changes for the API + report.
        """
        S = max(0.0, min(1.0, float(S)))
        b_q = question.get("irt", {}).get("b", 1300)
        topic = topic_of(question)
        R_old = session.ability

        # Global ability update.
        R_new, _, E = self._update_ability(R_old, b_q, S, session.n_answered, reliability)
        session.ability = round(R_new, 1)

        # Per-topic ability (report only; seeded from ability at first encounter).
        tr_old = session.topic_ability.get(topic, R_old)
        tr_new, _, _ = self._update_ability(tr_old, b_q, S, session.n_answered, reliability)
        session.topic_ability[topic] = round(tr_new, 1)

        # FSM transition (phase the item was asked under is recorded on the answer).
        asked_phase = session.fsm_phase
        new_phase, note = self._transition(session, S)
        session.fsm_phase = new_phase

        rec = AnswerRecord(
            question_id=question["id"], topic=topic, b_question=b_q,
            content_score=S, content_source=content_source, rubric=rubric,
            delivery=delivery or {}, transcript=transcript, fsm_phase=asked_phase,
        )
        rec.answered_at = time.time()
        session.answers.append(rec)
        session.n_answered += 1
        session.status = "active"

        return {
            "content_score": S, "expected": round(E, 4),
            "ability_before": round(R_old, 1), "ability_after": session.ability,
            "phase_before": asked_phase, "phase_after": new_phase,
            "phase_note": note, "topic": topic,
            "consecutive_high": session.consecutive_high,
            "consecutive_low": session.consecutive_low,
        }


# Singleton, mirroring the other interview services.
_engine_instance: Optional[AdaptiveEngine] = None


def get_adaptive_engine() -> AdaptiveEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = AdaptiveEngine()
    return _engine_instance
