"""
Stateless constrained-JSON grader for PLUTO vProctor (Tier-2 content eval).

This is a DELIBERATELY separate LLM path from core/brain.py's LLMReasoner:
  * no conversation history (grading must not be contaminated by prior turns),
  * temperature 0 (deterministic scoring),
  * Ollama `format=<json schema>` structured output + pydantic validation,
  * one retry on malformed/invalid output, then an honest failure.

It shares the resident qwen2.5:7b (Ollama, 127.0.0.1:11434) — no new GPU tenant.
The returned CONTENT score `S` in [0,1] is the ONLY signal the adaptive engine
consumes. Delivery/confidence is graded elsewhere and never merged into S.
"""
import json
import logging
from typing import List, Optional

from pydantic import BaseModel, Field, ValidationError, confloat

from core import config

logger = logging.getLogger(__name__)

OLLAMA_HOST = "http://127.0.0.1:11434"


class DimensionScore(BaseModel):
    name: str
    score: confloat(ge=0.0, le=1.0)     # normalized 0..1 for this rubric dimension
    justification: str = ""


class GradeResult(BaseModel):
    """Validated grader output. `content_score` is S in [0,1]."""
    content_score: confloat(ge=0.0, le=1.0)
    dimensions: List[DimensionScore] = Field(default_factory=list)
    covered_points: List[str] = Field(default_factory=list)
    missing_points: List[str] = Field(default_factory=list)
    red_flags: List[str] = Field(default_factory=list)
    is_non_answer: bool = False          # blank / "I don't know" / off-topic
    rationale: str = ""


# JSON Schema handed to Ollama `format=` so the model is constrained to emit
# exactly this shape. Derived from GradeResult but written explicitly so the
# wire contract is visible and stable.
GRADE_SCHEMA = {
    "type": "object",
    "properties": {
        "content_score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "dimensions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "justification": {"type": "string"},
                },
                "required": ["name", "score"],
            },
        },
        "covered_points": {"type": "array", "items": {"type": "string"}},
        "missing_points": {"type": "array", "items": {"type": "string"}},
        "red_flags": {"type": "array", "items": {"type": "string"}},
        "is_non_answer": {"type": "boolean"},
        "rationale": {"type": "string"},
    },
    "required": ["content_score", "is_non_answer"],
}

SYSTEM_PROMPT = (
    "You are a rigorous, fair technical interview grader. You score ONLY the "
    "correctness and completeness of the CANDIDATE ANSWER against the provided "
    "ideal answer points and rubric. You must ignore delivery, tone, grammar, "
    "confidence, and speaking style entirely — those are graded separately. "
    "A blank, evasive, or off-topic answer is a non-answer with content_score "
    "near 0. Do not reward fluent-sounding text that lacks substance. Respond "
    "with JSON only, matching the requested schema."
)


class JudgeLLM:
    """Stateless grader over the resident Ollama model."""

    def __init__(self, model: Optional[str] = None):
        self.model = model or config.LLM_MODEL_NAME

    def _build_prompt(self, question: dict, answer_text: str) -> str:
        rubric = question.get("scoring_rubric", {})
        ideal = question.get("ideal_answer_points", [])
        keywords = question.get("keywords", [])
        dims = [
            {"name": d.get("name"), "weight": d.get("weight"), "criteria": d.get("criteria")}
            for d in rubric.get("dimensions", [])
        ]
        payload = {
            "question": question.get("text", ""),
            "category": question.get("category"),
            "type": question.get("type"),
            "ideal_answer_points": ideal,
            "expected_keywords": keywords,
            "rubric_dimensions": dims,
            "red_flags_to_watch": rubric.get("red_flags", []),
            "candidate_answer": answer_text or "",
        }
        return (
            "Grade the candidate answer. Score each rubric dimension in [0,1], "
            "then set content_score in [0,1] as the weighted overall correctness. "
            "List which ideal points were covered vs missing. Flag red flags only "
            "if actually present. Set is_non_answer=true for blank/evasive/off-topic.\n\n"
            + json.dumps(payload, ensure_ascii=False, indent=2)
        )

    def grade(self, question: dict, answer_text: str) -> GradeResult:
        """Grade one answer. Retries once on malformed output; raises on failure.

        Returns a validated GradeResult. Callers own the fallback policy (e.g.
        drop back to the Tier-1 lexical score) if this raises.
        """
        import ollama

        client = ollama.Client(host=OLLAMA_HOST)
        prompt = self._build_prompt(question, answer_text)
        last_err: Optional[Exception] = None

        for attempt in (1, 2):
            try:
                resp = client.chat(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    format=GRADE_SCHEMA,      # structured-output constraint
                    options={
                        "temperature": 0.0,   # deterministic grading
                        "num_ctx": 4096,
                        "num_predict": 700,
                    },
                    keep_alive=300,
                )
                raw = resp.message.content
                return GradeResult.model_validate_json(raw)
            except (ValidationError, json.JSONDecodeError) as exc:
                last_err = exc
                logger.warning("Grader output invalid (attempt %d): %s", attempt, exc)
                # Nudge the retry to emit strict JSON.
                prompt = prompt + "\n\nYour previous output was not valid JSON for the schema. Return ONLY valid JSON."
            except Exception as exc:
                last_err = exc
                logger.error("Grader call failed (attempt %d): %s", attempt, exc)

        raise RuntimeError(f"JudgeLLM failed to grade after retries: {last_err}")


# Singleton, mirroring the other interview services.
_judge_instance: Optional[JudgeLLM] = None


def get_judge() -> JudgeLLM:
    global _judge_instance
    if _judge_instance is None:
        _judge_instance = JudgeLLM()
    return _judge_instance
