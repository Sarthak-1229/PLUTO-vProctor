"""
Session store for PLUTO vProctor.

Holds the *live* state of an interview session: the selected question pool,
per-topic Elo ratings, the confidence-building FSM phase, asked-question ids,
and the append-only answer log (CONTENT score + DESCRIPTIVE delivery signals,
kept on separate axes). In-memory only for the MVP, but hidden behind a
Repository interface so it can be swapped for SQLite/Redis without touching
callers. Mirrors the singleton accessor style of core/knowledge_base.py.

Design invariant carried from the plan: the FSM and difficulty engine read the
CONTENT score `S` ONLY. Delivery/confidence signals are stored for the final
descriptive report and MUST NOT drive question selection.
"""
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Ability seeds by self-declared seniority (Elo scale, see plan).
SENIORITY_SEED = {"junior": 1100, "mid": 1250, "senior": 1450}
DEFAULT_SEED = 1250

# Confidence-building FSM phases. Transitions are driven by CONTENT score S.
FSM_MEASURE = "MEASURE"      # probe near current ability (p* = 0.55)
FSM_REBUILD = "REBUILD"      # ease off to restore footing (p* = 0.80)
FSM_ESCALATE = "ESCALATE"    # push harder after a streak (p* = 0.40)
FSM_SWITCH = "SWITCH"        # change topic (stuck on current one)


@dataclass
class AnswerRecord:
    """One answered question. CONTENT and DELIVERY are deliberately separate."""
    question_id: str
    topic: str
    b_question: float                 # question difficulty at ask time (Elo b)
    # --- CONTENT axis (drives adaptation) ---
    content_score: Optional[float] = None    # S in [0,1]; None until graded
    content_source: str = "pending"          # tier1 | tier2_llm | pending
    rubric: Optional[dict] = None             # per-dimension breakdown (tier2)
    # --- DELIVERY axis (descriptive report only, never adapts difficulty) ---
    delivery: dict = field(default_factory=dict)  # e.g. wpm, filler_rate, pauses
    transcript: str = ""
    asked_at: float = field(default_factory=lambda: time.time())
    answered_at: Optional[float] = None
    fsm_phase: str = FSM_MEASURE      # phase active when this item was served


@dataclass
class InterviewSession:
    session_id: str
    target_role: str = "*"
    seniority: str = "mid"
    resume_tags: List[str] = field(default_factory=list)
    pool_ids: List[str] = field(default_factory=list)       # selected candidate pool
    asked_ids: List[str] = field(default_factory=list)      # order served
    ability: float = DEFAULT_SEED                            # global Elo R_u
    topic_ability: Dict[str, float] = field(default_factory=dict)  # per-topic R_u
    fsm_phase: str = FSM_MEASURE
    current_topic: str = ""           # topic bucket currently being probed
    consecutive_low: int = 0          # streak of low CONTENT scores (for REBUILD/SWITCH)
    consecutive_high: int = 0         # streak of high CONTENT scores (for ESCALATE)
    n_answered: int = 0
    answers: List[AnswerRecord] = field(default_factory=list)
    created_at: float = field(default_factory=lambda: time.time())
    status: str = "created"           # created | active | completed
    consent: dict = field(default_factory=dict)  # per-stream revocable flags

    def to_public(self) -> dict:
        """Serialisable view for API responses (dataclasses -> plain dict)."""
        d = asdict(self)
        return d


class SessionRepository:
    """Interface so the in-memory impl can be swapped without caller changes."""

    def create(self, **kwargs) -> InterviewSession:
        raise NotImplementedError

    def get(self, session_id: str) -> Optional[InterviewSession]:
        raise NotImplementedError

    def save(self, session: InterviewSession) -> None:
        raise NotImplementedError

    def delete(self, session_id: str) -> bool:
        raise NotImplementedError

    def list_ids(self) -> List[str]:
        raise NotImplementedError


class InMemorySessionStore(SessionRepository):
    """Process-local dict store. State is lost on restart — fine for the MVP."""

    def __init__(self):
        self._sessions: Dict[str, InterviewSession] = {}

    def create(self, target_role: str = "*", seniority: str = "mid",
               resume_tags: Optional[List[str]] = None,
               pool_ids: Optional[List[str]] = None,
               consent: Optional[dict] = None) -> InterviewSession:
        sid = uuid.uuid4().hex
        seed = SENIORITY_SEED.get((seniority or "mid").lower(), DEFAULT_SEED)
        session = InterviewSession(
            session_id=sid,
            target_role=target_role or "*",
            seniority=(seniority or "mid").lower(),
            resume_tags=list(resume_tags or []),
            pool_ids=list(pool_ids or []),
            ability=seed,
            consent=dict(consent or {}),
        )
        self._sessions[sid] = session
        logger.info("Interview session created: %s (role=%s, seed=%d)", sid, target_role, seed)
        return session

    def get(self, session_id: str) -> Optional[InterviewSession]:
        return self._sessions.get(session_id)

    def save(self, session: InterviewSession) -> None:
        self._sessions[session.session_id] = session

    def delete(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None

    def list_ids(self) -> List[str]:
        return list(self._sessions.keys())


# Singleton, mirroring get_knowledge_base()
_store_instance: Optional[InMemorySessionStore] = None


def get_session_store() -> InMemorySessionStore:
    global _store_instance
    if _store_instance is None:
        _store_instance = InMemorySessionStore()
    return _store_instance
