"""
Delivery-signal fusion for PLUTO vProctor (Part 5).

Fuses the two DESCRIPTIVE delivery streams into plain, non-judgmental
observations for the practice report:
  * speech   — stt_service.DeliverySignals (words-per-minute, filler rate,
               long pauses, mean inter-word gap),
  * body     — in-browser MediaPipe aggregates computed client-side
               (face-present ratio, head-motion magnitude, centered ratio).

HARD invariant (from the plan): everything here is DESCRIPTIVE. It reports what
was measured and NEVER infers emotion, nervousness, confidence, honesty, or
hireability, and NEVER feeds the difficulty/FSM engine — that engine reads the
CONTENT score S alone. The wording below is deliberately factual (numbers, not
verdicts) so a reader draws their own conclusions.
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "Delivery metrics are DESCRIPTIVE observations of speech and on-camera "
    "presence only. They are not a measure of confidence, nervousness, emotion, "
    "honesty, or interview-readiness, and they never affect how answers are scored."
)


def _round(x: Optional[float], n: int = 1) -> Optional[float]:
    return round(float(x), n) if isinstance(x, (int, float)) else None


class DeliveryAnalyzer:
    """Stateless fuser of descriptive speech + body signals. No verdicts."""

    # ---- single-answer descriptions --------------------------------------
    def describe_speech(self, speech: Dict[str, Any]) -> List[str]:
        out: List[str] = []
        if not speech:
            return out
        wpm = speech.get("words_per_minute")
        if wpm:
            out.append(f"Spoke at about {round(wpm)} words per minute.")
        wc = speech.get("word_count")
        if wc:
            out.append(f"Answer length was {int(wc)} spoken words.")
        fr = speech.get("filler_rate_per_min")
        fc = speech.get("filler_count")
        if fc is not None:
            rate = f" (~{round(fr)}/min)" if fr else ""
            out.append(f"Used {int(fc)} filler words such as 'um' or 'like'{rate}.")
        lp = speech.get("long_pause_count")
        if lp:
            out.append(f"Paused for over 1.5s on {int(lp)} occasion(s).")
        return out

    def describe_body(self, body: Dict[str, Any]) -> List[str]:
        out: List[str] = []
        if not body:
            return out
        fpr = body.get("face_present_ratio")
        if fpr is not None:
            out.append(f"A face was detected in {round(fpr * 100)}% of sampled camera frames.")
        cr = body.get("centered_ratio")
        if cr is not None:
            out.append(f"Face stayed near the centre of frame {round(cr * 100)}% of the time.")
        mm = body.get("mean_motion")
        if mm is not None:
            out.append(f"Average head-movement magnitude was {_round(mm, 3)} (normalized units).")
        return out

    # ---- session aggregation ---------------------------------------------
    def summarize_session(self, answers: List[Any]) -> Dict[str, Any]:
        """Aggregate descriptive delivery across a session's answer records.

        `answers` may be AnswerRecord dataclasses or plain dicts; each is
        expected to carry a `delivery` mapping of {"speech": {...}, "body": {...}}.
        """
        wpms: List[float] = []
        filler_rates: List[float] = []
        long_pauses: List[int] = []
        face_ratios: List[float] = []
        centered: List[float] = []
        motions: List[float] = []
        speech_answers = 0
        body_answers = 0

        for rec in answers:
            delivery = rec.get("delivery", {}) if isinstance(rec, dict) else getattr(rec, "delivery", {})
            speech = (delivery or {}).get("speech") or {}
            body = (delivery or {}).get("body") or {}
            if speech:
                speech_answers += 1
                if speech.get("words_per_minute"):
                    wpms.append(speech["words_per_minute"])
                if speech.get("filler_rate_per_min") is not None:
                    filler_rates.append(speech["filler_rate_per_min"])
                if speech.get("long_pause_count") is not None:
                    long_pauses.append(speech["long_pause_count"])
            if body:
                body_answers += 1
                if body.get("face_present_ratio") is not None:
                    face_ratios.append(body["face_present_ratio"])
                if body.get("centered_ratio") is not None:
                    centered.append(body["centered_ratio"])
                if body.get("mean_motion") is not None:
                    motions.append(body["mean_motion"])

        def _avg(xs):
            return round(sum(xs) / len(xs), 2) if xs else None

        return {
            "disclaimer": DISCLAIMER,
            "speech": {
                "answers_with_speech_signal": speech_answers,
                "mean_words_per_minute": _avg(wpms),
                "mean_filler_rate_per_min": _avg(filler_rates),
                "total_long_pauses": sum(long_pauses) if long_pauses else 0,
            },
            "body": {
                "answers_with_body_signal": body_answers,
                "mean_face_present_ratio": _avg(face_ratios),
                "mean_centered_ratio": _avg(centered),
                "mean_head_motion": _avg(motions),
            },
        }


# Singleton, mirroring the other interview services.
_analyzer_instance: Optional[DeliveryAnalyzer] = None


def get_delivery_analyzer() -> DeliveryAnalyzer:
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = DeliveryAnalyzer()
    return _analyzer_instance
