"""
Question bank repository for PLUTO vProctor.

Loads data/question_bank.json + data/skill_taxonomy.json and provides read
access, resume-driven selection (explainable, CPU-only, lexical MVP), and the
difficulty helpers the adaptive engine needs. Mirrors the singleton +
JSON-persistence pattern of core/knowledge_base.py.
"""
import json
import logging
from pathlib import Path
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)

# Authored difficulty tier -> Elo b seed (see design / question_schema irt.b)
TIER_TO_B = {1: 1000, 2: 1150, 3: 1300, 4: 1450, 5: 1600}

# Coverage quotas so a session is never all-technical.
DEFAULT_QUOTAS = {"behavioral": 4, "hr_culture": 2, "situational": 2}

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class QuestionBank:
    """In-memory repository over the curated question bank."""

    def __init__(self, bank_path: Optional[Path] = None,
                 taxonomy_path: Optional[Path] = None):
        self.bank_path = Path(bank_path) if bank_path else DATA_DIR / "question_bank.json"
        self.taxonomy_path = Path(taxonomy_path) if taxonomy_path else DATA_DIR / "skill_taxonomy.json"
        self._bank = self._load(self.bank_path, default={"questions": []})
        self._taxonomy = self._load(self.taxonomy_path, default={"roles": {}, "skills": {}})
        self._by_id: Dict[str, dict] = {q["id"]: q for q in self._bank.get("questions", [])}
        # Merge the optional auto-generated bank (dataset-import). Kept in a
        # SEPARATE file so the curated 106 stay pristine and reversible; the
        # curated item always wins on any id collision.
        self._merge_generated()
        # Build a surface-form -> canonical skill slug alias map for resume grounding.
        self._alias_map = self._build_alias_map()
        logger.info("QuestionBank loaded: %d questions", len(self._by_id))

    @staticmethod
    def _load(path: Path, default: dict) -> dict:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as exc:
                logger.error("Failed to load %s: %s", path, exc)
        else:
            logger.warning("Missing data file: %s", path)
        return default

    def _build_alias_map(self) -> Dict[str, str]:
        amap = {}
        for slug, meta in self._taxonomy.get("skills", {}).items():
            amap[slug.lower()] = slug
            for alias in meta.get("aliases", []):
                amap[alias.lower()] = slug
        return amap

    def _merge_generated(self) -> None:
        """Fold data/question_bank_generated.json into the in-memory bank.

        The generated file (source="dataset-import") is auto-enriched and kept
        apart from the curated bank. Curated ids take precedence: a generated
        item whose id already exists is skipped, so re-generating can never
        clobber a hand-authored question.
        """
        gen_path = self.bank_path.parent / "question_bank_generated.json"
        if not gen_path.exists():
            return
        gen = self._load(gen_path, default={"questions": []})
        merged = skipped = 0
        for q in gen.get("questions", []):
            qid = q.get("id")
            if not qid:
                continue
            if qid in self._by_id:
                logger.warning("Generated id %s collides with curated bank; keeping curated", qid)
                skipped += 1
                continue
            self._by_id[qid] = q
            self._bank.setdefault("questions", []).append(q)
            merged += 1
        logger.info("Merged %d generated questions (%d skipped on collision)", merged, skipped)

    # ---- read access -------------------------------------------------------
    def all_questions(self) -> List[dict]:
        return list(self._by_id.values())

    def get(self, qid: str) -> Optional[dict]:
        return self._by_id.get(qid)

    def by_category(self, category: str) -> List[dict]:
        return [q for q in self._by_id.values() if q.get("category") == category]

    # ---- resume grounding --------------------------------------------------
    def normalize_skills(self, surface_terms: List[str]) -> List[str]:
        """Map free-text resume skill mentions to canonical taxonomy slugs."""
        out = []
        for term in surface_terms:
            slug = self._alias_map.get(term.strip().lower())
            if slug and slug not in out:
                out.append(slug)
        return out

    # ---- selection ---------------------------------------------------------
    def _score(self, q: dict, resume_tags: set, target_role: str) -> float:
        role_fit = q.get("role_fit", [])
        role_hit = 1.0 if (target_role in role_fit or "*" in role_fit) else 0.0
        qtags = set(q.get("tags", []))
        overlap = len(resume_tags & qtags) / max(1, len(qtags)) if qtags else 0.0
        # sem_sim (MiniLM cosine) is an optional booster deferred to a later phase.
        sem_sim = 0.0
        return 1.0 * role_hit + 0.6 * overlap + 0.3 * sem_sim

    def select_for_resume(self, resume_tags: List[str], target_role: str = "*",
                          limit: int = 15, quotas: Optional[Dict[str, int]] = None) -> List[dict]:
        """Return a ranked, quota-satisfied pool of questions for a resume.

        Scoring: score(q) = 1.0*role_hit + 0.6*tag_overlap + 0.3*sem_sim.
        Quotas guarantee a minimum number from key non-technical categories.
        The adaptive engine then orders *within* this pool by ability match.
        """
        quotas = quotas if quotas is not None else DEFAULT_QUOTAS
        rtags = set(resume_tags or [])

        # AIML hook (feature-flagged, graceful fallback): model pool assembly as a
        # CSP (backtracking + forward-checking) over category quotas / difficulty
        # spread / uniqueness, then optimize résumé coverage + diversity with Local
        # Search + a Genetic Algorithm. get_csp_selector() is None when
        # AIML_CSP_ENABLED is off, and select() returns None if the CSP is
        # infeasible, so either way we drop to the greedy quota selector below.
        try:
            from core.aiml.selection_csp import get_csp_selector
            sel = get_csp_selector()
            if sel is not None:
                res = sel.select(self.all_questions(), target_role=target_role,
                                 resume_tags=list(rtags), limit=limit, quotas=quotas)
                if res is not None:
                    pool = [self._by_id[i] for i in res[0] if i in self._by_id]
                    if pool:
                        logger.info("CSP pool assembly: %d questions (%s)",
                                    len(pool), res[1]["fitness"])
                        return pool
        except Exception:
            logger.debug("AIML CSP selection unavailable; greedy fallback",
                         exc_info=True)

        scored = sorted(
            self._by_id.values(),
            key=lambda q: self._score(q, rtags, target_role),
            reverse=True,
        )

        chosen: List[dict] = []
        chosen_ids = set()

        # 1) satisfy category quotas first (highest-scored within each category)
        for cat, need in quotas.items():
            picked = 0
            for q in scored:
                if picked >= need:
                    break
                if q.get("category") == cat and q["id"] not in chosen_ids:
                    chosen.append(q)
                    chosen_ids.add(q["id"])
                    picked += 1

        # 2) fill remaining slots by global score
        for q in scored:
            if len(chosen) >= limit:
                break
            if q["id"] not in chosen_ids:
                chosen.append(q)
                chosen_ids.add(q["id"])

        return chosen[:limit]

    def nearest_by_difficulty(self, b_target: float, pool_ids: List[str],
                              exclude_ids: set) -> Optional[dict]:
        """Pick the unused question in the pool whose irt.b is nearest b_target."""
        candidates = [
            self._by_id[i] for i in pool_ids
            if i in self._by_id and i not in exclude_ids
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda q: abs(q.get("irt", {}).get("b", 1300) - b_target))


# Singleton, mirroring get_knowledge_base()
_bank_instance: Optional[QuestionBank] = None


def get_question_bank() -> QuestionBank:
    global _bank_instance
    if _bank_instance is None:
        _bank_instance = QuestionBank()
    return _bank_instance
