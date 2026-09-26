"""
Tier-1 content scorer for PLUTO vProctor (fast, synchronous, CPU-only).

Produces a PROVISIONAL correctness signal S in [0,1] the instant an answer is
transcribed, so the next question can be chosen without waiting on the LLM.
It combines expected-keyword coverage with ideal-answer-point coverage and a
non-answer guard. Tier-2 (judge_llm) later refines/overrides S asynchronously.

Caveat carried from the plan: coverage is only a PROXY for correctness. Tier-1
is deliberately conservative and is superseded by the Tier-2 rubric grade when
that arrives; never treat Tier-1 alone as a final verdict.
"""
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

MIN_WORDS = 4
NON_ANSWER_RE = re.compile(
    r"\b(i (don'?t|do not) know|no idea|not sure|no clue|skip( this)?|pass|"
    r"can'?t answer|dunno|n/?a)\b", re.IGNORECASE)
_STOP = {"the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for",
         "with", "is", "are", "be", "as", "at", "by", "it", "this", "that",
         "you", "your", "we", "i", "they", "how", "what", "why", "when"}


def _fuzzy():
    """Return a token similarity fn in [0,1]; rapidfuzz if present, else stdlib."""
    try:
        from rapidfuzz import fuzz
        return lambda a, b: fuzz.ratio(a, b) / 100.0
    except ImportError:
        from difflib import SequenceMatcher
        return lambda a, b: SequenceMatcher(None, a, b).ratio()


@dataclass
class Tier1Result:
    content_score: float
    is_non_answer: bool
    keyword_coverage: float
    ideal_coverage: float
    matched_keywords: List[str] = field(default_factory=list)
    covered_points: List[str] = field(default_factory=list)
    word_count: int = 0
    source: str = "tier1"


class Tier1Evaluator:
    def __init__(self):
        self._ratio = _fuzzy()

    @staticmethod
    def _tokens(text_low: str) -> List[str]:
        return [t for t in re.findall(r"[a-z0-9+#.]+", text_low) if t]

    def _kw_hit(self, kw: str, text_low: str, tokens: List[str]) -> bool:
        kw = kw.lower().strip()
        if not kw:
            return False
        if kw in text_low:                      # substring covers multiword keywords
            return True
        return any(self._ratio(kw, tok) >= 0.86 for tok in tokens)  # typo tolerance

    def keyword_coverage(self, text_low, tokens, keywords):
        if not keywords:
            return 1.0, []
        matched = [k for k in keywords if self._kw_hit(k, text_low, tokens)]
        return len(matched) / len(keywords), matched

    def ideal_coverage(self, text_low, points):
        """A point counts as covered if >=50% of its content words appear."""
        if not points:
            return 1.0, []
        covered = []
        for pt in points:
            words = [w for w in re.findall(r"[a-z0-9+#]+", pt.lower())
                     if len(w) > 3 and w not in _STOP]
            if not words:
                continue
            hits = sum(1 for w in words if w in text_low)
            if hits / len(words) >= 0.5:
                covered.append(pt)
        denom = len([p for p in points if p]) or 1
        return len(covered) / denom, covered

    def score(self, question: dict, answer_text: str) -> Tier1Result:
        text = (answer_text or "").strip()
        text_low = text.lower()
        tokens = self._tokens(text_low)
        wc = len(tokens)

        if wc < MIN_WORDS or NON_ANSWER_RE.search(text_low):
            return Tier1Result(content_score=0.02, is_non_answer=True,
                               keyword_coverage=0.0, ideal_coverage=0.0,
                               word_count=wc)

        kw_cov, matched = self.keyword_coverage(
            text_low, tokens, question.get("keywords", []))
        ideal_cov, covered = self.ideal_coverage(
            text_low, question.get("ideal_answer_points", []))
        s = max(0.0, min(1.0, 0.5 * kw_cov + 0.5 * ideal_cov))
        return Tier1Result(content_score=round(s, 4), is_non_answer=False,
                           keyword_coverage=round(kw_cov, 4),
                           ideal_coverage=round(ideal_cov, 4),
                           matched_keywords=matched, covered_points=covered,
                           word_count=wc)


# Singleton, mirroring the other interview services.
_eval_instance: Optional[Tier1Evaluator] = None


def get_tier1_evaluator() -> Tier1Evaluator:
    global _eval_instance
    if _eval_instance is None:
        _eval_instance = Tier1Evaluator()
    return _eval_instance
