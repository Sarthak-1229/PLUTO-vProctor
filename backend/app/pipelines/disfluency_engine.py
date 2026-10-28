"""Disfluency analysis engine for PLUTO vProctor.

Analyzes ASR transcript words and acoustic filler detections to identify:
- Hard fillers ("um", "uh", "umm", "err", etc.)
- Soft fillers ("like", "so", "actually", etc. with grammatical context filtering)
- Phrase fillers ("you know", "i mean", "to be honest", etc. using KMP search)
- Pauses and hesitations (sentence boundaries, hesitations, long pauses, late start)
- Speaking pace (WPM) and pace bands
- Timed fluency deductions with explainability
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.app.algorithms.edit_distance import levenshtein
from backend.app.algorithms.string_match import kmp_search
from backend.app.config import settings
from backend.app.pipelines.asr import Word, WordSource


@dataclass
class DisfluencyEvent:
    """An individual disfluency occurrence (filler or pause)."""
    event_type: str  # "filler", "pause", "pace", "late_start"
    sub_type: str  # "hard", "soft", "phrase", "acoustic", "hesitation", "long_pause", "slow", "fast"
    start: float  # seconds on recording clock
    end: float
    duration: float
    text: str
    confidence: float
    deduction: float
    reason: str
    question_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "sub_type": self.sub_type,
            "start": round(self.start, 2),
            "end": round(self.end, 2),
            "duration": round(self.duration, 2),
            "text": self.text,
            "confidence": round(self.confidence, 2),
            "deduction": round(self.deduction, 2),
            "reason": self.reason,
            "question_id": self.question_id,
        }


@dataclass
class DisfluencyAnalysisResult:
    """Complete disfluency analysis for an answer or interview."""
    words: List[Word] = field(default_factory=list)
    events: List[DisfluencyEvent] = field(default_factory=list)
    hard_filler_count: int = 0
    soft_filler_count: int = 0
    phrase_filler_count: int = 0
    acoustic_filler_count: int = 0
    hesitation_count: int = 0
    long_pause_count: int = 0
    total_pause_duration: float = 0.0
    word_count: int = 0
    speaking_duration_sec: float = 0.0
    pace_wpm: float = 0.0
    pace_band: str = "normal"
    fillers_per_minute: float = 0.0
    total_deduction: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hard_filler_count": self.hard_filler_count,
            "soft_filler_count": self.soft_filler_count,
            "phrase_filler_count": self.phrase_filler_count,
            "acoustic_filler_count": self.acoustic_filler_count,
            "hesitation_count": self.hesitation_count,
            "long_pause_count": self.long_pause_count,
            "total_pause_duration": round(self.total_pause_duration, 2),
            "word_count": self.word_count,
            "speaking_duration_sec": round(self.speaking_duration_sec, 2),
            "pace_wpm": round(self.pace_wpm, 1),
            "pace_band": self.pace_band,
            "fillers_per_minute": round(self.fillers_per_minute, 1),
            "total_deduction": round(self.total_deduction, 2),
            "events": [e.to_dict() for e in self.events],
        }


class DisfluencyEngine:
    """Engine for disfluency, pause, pace and filler detection."""

    def __init__(self, config_path: Optional[Path] = None):
        cfg_path = config_path or (
            settings.BASE_DIR / "backend" / "app" / "config" / "disfluency.json"
        )
        with open(cfg_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.hard_fillers: Set[str] = set(self.config.get("hard_fillers", []))
        self.hard_fuzzy_targets: List[str] = self.config.get("hard_filler_fuzzy_targets", [])
        self.soft_fillers: Set[str] = set(self.config.get("soft_fillers", []))
        self.phrase_fillers: List[str] = self.config.get("phrase_fillers", [])
        self.pause_thresholds: Dict[str, float] = self.config.get("pause_thresholds", {})
        self.pace_bands: Dict[str, float] = self.config.get("pace_bands", {})
        self.penalties: Dict[str, float] = self.config.get("penalties", {})

    def merge_words(
        self, asr_words: List[Word], acoustic_words: List[Word]
    ) -> List[Word]:
        """Merge ASR words and acoustic fillers, deduplicating overlaps."""
        merged: List[Word] = list(asr_words)

        for ac in acoustic_words:
            # Check overlap with any existing word
            overlap_found = False
            for w in asr_words:
                inter_s = max(ac.start, w.start)
                inter_e = min(ac.end, w.end)
                if inter_e > inter_s:
                    overlap_dur = inter_e - inter_s
                    ac_dur = max(0.001, ac.end - ac.start)
                    if overlap_dur / ac_dur > 0.3:
                        overlap_found = True
                        break
            if not overlap_found:
                merged.append(ac)

        merged.sort(key=lambda w: w.start)
        return merged

    COMMON_ENGLISH_WORDS: Set[str] = {
        "a", "i", "an", "am", "at", "as", "he", "hi", "ha", "me", "my",
        "no", "on", "or", "so", "to", "up", "us", "we", "in", "it", "is",
        "if", "him", "her", "his", "the", "and", "but", "for", "out"
    }

    def is_hard_filler(self, text: str) -> bool:
        """Check exact match or 1-edit-distance fuzzy match for hard fillers."""
        clean = text.strip().lower()
        if not clean:
            return False
        if clean in self.hard_fillers:
            return True
        if clean in self.COMMON_ENGLISH_WORDS:
            return False
        if len(clean) >= 3:
            for target in self.hard_fuzzy_targets:
                if abs(len(clean) - len(target)) <= 1:
                    if levenshtein(clean, target) <= 1:
                        return True
        return False

    def is_soft_filler(
        self,
        word_idx: int,
        words: List[Word],
    ) -> Tuple[bool, str]:
        """Context-aware classification of soft filler words.

        Prevents false positives:
        - "like" as verb: "I like python", "they like that"
        - "like" as comparison: "looks like", "sounds like"
        - "so" starting direct clause: "so that", "so we"
        """
        w = words[word_idx]
        text = w.text.strip().lower()
        if text not in self.soft_fillers:
            return False, ""

        prev_w = words[word_idx - 1] if word_idx > 0 else None
        next_w = words[word_idx + 1] if word_idx + 1 < len(words) else None

        # Context rules for 'like'
        if text == "like":
            if prev_w and prev_w.text.lower() in {"i", "we", "they", "you", "would"}:
                return False, "verb_usage"
            if prev_w and prev_w.text.lower() in {"looks", "sounds", "feels", "seemed", "acts", "something"}:
                return False, "comparison_usage"
            # If followed by a pause or preceded by a pause
            is_flanked_by_pause = False
            if prev_w and (w.start - prev_w.end) >= 0.35:
                is_flanked_by_pause = True
            if next_w and (next_w.start - w.end) >= 0.35:
                is_flanked_by_pause = True
            if prev_w is None or next_w is None or is_flanked_by_pause:
                return True, "hesitation_like"
            # If followed by another filler
            if next_w and next_w.text.lower() in self.hard_fillers | self.soft_fillers:
                return True, "clustered_like"
            return False, "normal_speech"

        # Context rules for 'so'
        if text == "so":
            if next_w and next_w.text.lower() in {"that", "much", "many", "far"}:
                return False, "adverb_conjunction"
            # Paused 'so...' or leading 'so...'
            if prev_w is None or (prev_w and (w.start - prev_w.end) >= 0.4):
                if next_w and (next_w.start - w.end) >= 0.35:
                    return True, "standalone_so"
            return False, "conjunction"

        # Words like 'basically', 'actually', 'literally', 'honestly'
        if text in {"basically", "actually", "literally", "honestly", "seriously"}:
            # Often used as crutch words in tech interviews
            return True, f"crutch_{text}"

        return False, "normal"

    def detect_phrase_fillers(self, words: List[Word]) -> List[DisfluencyEvent]:
        """Detect multi-word phrase fillers using KMP search on word sequence."""
        if not words:
            return []

        word_texts = [w.text.lower() for w in words]
        joined = " ".join(word_texts)
        phrase_events: List[DisfluencyEvent] = []

        for phrase in self.phrase_fillers:
            p_len = len(phrase.split())
            p_str = phrase.lower()
            # Search occurrences using KMP on the joined text
            matches = kmp_search(joined, p_str)
            for m in matches:
                # Map character position back to word indices
                prefix = joined[:m]
                start_w_idx = len(prefix.split()) if prefix.strip() else 0
                end_w_idx = start_w_idx + p_len - 1

                if 0 <= start_w_idx < len(words) and end_w_idx < len(words):
                    matched_words = words[start_w_idx : end_w_idx + 1]
                    matched_phrase = " ".join(w.text for w in matched_words)
                    if matched_phrase.lower() == p_str:
                        p_start = matched_words[0].start
                        p_end = matched_words[-1].end
                        phrase_events.append(
                            DisfluencyEvent(
                                event_type="filler",
                                sub_type="phrase",
                                start=p_start,
                                end=p_end,
                                duration=round(p_end - p_start, 2),
                                text=matched_phrase,
                                confidence=0.95,
                                deduction=self.penalties.get("phrase_filler_each", 0.5),
                                reason=f"Phrase filler '{p_str}'",
                            )
                        )
        return phrase_events

    def analyze(
        self,
        asr_words: List[Word],
        acoustic_words: Optional[List[Word]] = None,
        *,
        question_start_sec: Optional[float] = None,
        question_id: Optional[str] = None,
    ) -> DisfluencyAnalysisResult:
        """Run complete disfluency and fluency analysis."""
        words = self.merge_words(asr_words, acoustic_words or [])
        events: List[DisfluencyEvent] = []

        if not words:
            return DisfluencyAnalysisResult(words=words)

        # 1. Late start detection
        if question_start_sec is not None:
            late_start_threshold = self.pause_thresholds.get("late_start_sec", 3.0)
            initial_delay = words[0].start - question_start_sec
            if initial_delay > late_start_threshold:
                events.append(
                    DisfluencyEvent(
                        event_type="late_start",
                        sub_type="late_start",
                        start=question_start_sec,
                        end=words[0].start,
                        duration=round(initial_delay, 2),
                        text=f"[late start: {round(initial_delay, 1)}s]",
                        confidence=1.0,
                        deduction=self.penalties.get("late_start_each", 1.5),
                        reason=f"Started answering {round(initial_delay, 1)}s after question",
                        question_id=question_id,
                    )
                )

        # 2. Phrase fillers
        phrase_events = self.detect_phrase_fillers(words)
        events.extend(phrase_events)
        phrase_word_indices: Set[int] = set()
        for pe in phrase_events:
            for i, w in enumerate(words):
                if pe.start <= w.start and w.end <= pe.end:
                    phrase_word_indices.add(i)

        # 3. Word-level fillers
        hard_count = 0
        soft_count = 0
        acoustic_count = 0

        for i, w in enumerate(words):
            if i in phrase_word_indices:
                continue

            if w.source == WordSource.ACOUSTIC:
                acoustic_count += 1
                w.is_filler = True
                w.filler_type = "acoustic"
                events.append(
                    DisfluencyEvent(
                        event_type="filler",
                        sub_type="acoustic",
                        start=w.start,
                        end=w.end,
                        duration=round(w.end - w.start, 2),
                        text="[um/uh]",
                        confidence=w.confidence,
                        deduction=self.penalties.get("hard_filler_per_100_words", 1.5) * 0.5,
                        reason="Acoustic nasal filled-pause detected",
                        question_id=question_id,
                    )
                )
            elif self.is_hard_filler(w.text):
                hard_count += 1
                w.is_filler = True
                w.filler_type = "hard"
                events.append(
                    DisfluencyEvent(
                        event_type="filler",
                        sub_type="hard",
                        start=w.start,
                        end=w.end,
                        duration=round(w.end - w.start, 2),
                        text=w.text,
                        confidence=w.confidence,
                        deduction=self.penalties.get("hard_filler_per_100_words", 1.5) * 0.5,
                        reason=f"Hard filler '{w.text}'",
                        question_id=question_id,
                    )
                )
            else:
                is_soft, reason = self.is_soft_filler(i, words)
                if is_soft:
                    soft_count += 1
                    w.is_filler = True
                    w.filler_type = "soft"
                    events.append(
                        DisfluencyEvent(
                            event_type="filler",
                            sub_type="soft",
                            start=w.start,
                            end=w.end,
                            duration=round(w.end - w.start, 2),
                            text=w.text,
                            confidence=w.confidence,
                            deduction=self.penalties.get("soft_filler_per_100_words", 0.5) * 0.5,
                            reason=f"Crutch word '{w.text}' ({reason})",
                            question_id=question_id,
                        )
                    )

        # 4. Pause and hesitation detection between words
        hesitation_min = self.pause_thresholds.get("hesitation_min_sec", 0.6)
        long_pause_min = self.pause_thresholds.get("long_pause_min_sec", 1.2)
        total_pause_duration = 0.0
        hesitation_count = 0
        long_pause_count = 0

        for i in range(len(words) - 1):
            curr_w = words[i]
            next_w = words[i + 1]
            gap = next_w.start - curr_w.end

            if gap >= hesitation_min:
                total_pause_duration += gap
                if gap >= long_pause_min:
                    long_pause_count += 1
                    events.append(
                        DisfluencyEvent(
                            event_type="pause",
                            sub_type="long_pause",
                            start=curr_w.end,
                            end=next_w.start,
                            duration=round(gap, 2),
                            text=f"[long pause: {round(gap, 1)}s]",
                            confidence=1.0,
                            deduction=self.penalties.get("long_pause_each", 1.0),
                            reason=f"Long silence of {round(gap, 1)}s during speech",
                            question_id=question_id,
                        )
                    )
                else:
                    hesitation_count += 1
                    events.append(
                        DisfluencyEvent(
                            event_type="pause",
                            sub_type="hesitation",
                            start=curr_w.end,
                            end=next_w.start,
                            duration=round(gap, 2),
                            text=f"[hesitation: {round(gap, 1)}s]",
                            confidence=1.0,
                            deduction=self.penalties.get("hesitation_each", 0.3),
                            reason=f"Hesitation pause of {round(gap, 1)}s",
                            question_id=question_id,
                        )
                    )

        # 5. Speaking pace calculation
        norm_words = [w for w in words if w.source == WordSource.ASR]
        word_count = len(norm_words)
        speaking_dur = max(1.0, words[-1].end - words[0].start)
        duration_min = speaking_dur / 60.0
        pace_wpm = (word_count / duration_min) if duration_min > 0 else 0.0

        # Determine pace band
        bands = self.pace_bands
        pace_band = "normal"
        if pace_wpm < bands.get("very_slow_wpm", 80):
            pace_band = "very_slow"
        elif pace_wpm < bands.get("slow_wpm", 100):
            pace_band = "slow"
        elif pace_wpm > bands.get("very_fast_wpm", 210):
            pace_band = "very_fast"
        elif pace_wpm > bands.get("fast_wpm", 180):
            pace_band = "fast"

        if pace_band in {"slow", "very_slow", "fast", "very_fast"}:
            events.append(
                DisfluencyEvent(
                    event_type="pace",
                    sub_type=pace_band,
                    start=words[0].start,
                    end=words[-1].end,
                    duration=round(speaking_dur, 2),
                    text=f"[{round(pace_wpm, 1)} WPM ({pace_band})]",
                    confidence=1.0,
                    deduction=self.penalties.get("pace_deviation_per_band", 1.0),
                    reason=f"Pace is {pace_band} ({round(pace_wpm, 1)} WPM; ideal is 100-160 WPM)",
                    question_id=question_id,
                )
            )

        # Total deductions with free allowance and cap
        total_fillers = hard_count + acoustic_count
        allowance = int(self.penalties.get("hard_filler_free_allowance_per_answer", 1))
        # Deduct allowance from earliest hard fillers if any
        if allowance > 0 and total_fillers > 0:
            allowed = 0
            for ev in events:
                if ev.event_type == "filler" and ev.sub_type in {"hard", "acoustic"} and allowed < allowance:
                    ev.deduction = 0.0
                    ev.reason += " (Free allowance)"
                    allowed += 1

        raw_deductions = sum(ev.deduction for ev in events)
        max_deduction = self.penalties.get("max_fluency_deduction_per_answer", 8.0)
        total_deduction = min(max_deduction, raw_deductions)

        fillers_per_min = (total_fillers + soft_count + len(phrase_events)) / max(0.1, duration_min)

        return DisfluencyAnalysisResult(
            words=words,
            events=events,
            hard_filler_count=hard_count,
            soft_filler_count=soft_count,
            phrase_filler_count=len(phrase_events),
            acoustic_filler_count=acoustic_count,
            hesitation_count=hesitation_count,
            long_pause_count=long_pause_count,
            total_pause_duration=round(total_pause_duration, 2),
            word_count=word_count,
            speaking_duration_sec=round(speaking_dur, 2),
            pace_wpm=round(pace_wpm, 1),
            pace_band=pace_band,
            fillers_per_minute=round(fillers_per_min, 1),
            total_deduction=round(total_deduction, 2),
        )
