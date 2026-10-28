"""Deepgram hosted ASR provider for PLUTO vProctor.

Uses Deepgram Nova-2 API with native filler word detection (filler_words=true)
and word-level timestamps.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from backend.app.pipelines.asr import (
    ASRProvider, Segment, TranscriptionResult, Word, WordSource,
)


class DeepgramASRProvider(ASRProvider):
    """Hosted ASR provider using Deepgram Nova-2 API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("DEEPGRAM_API_KEY", "")
        self.api_url = "https://api.deepgram.com/v1/listen"

    @property
    def name(self) -> str:
        return "deepgram"

    def is_available(self) -> bool:
        return bool(self.api_key.strip())

    def transcribe(
        self,
        audio_path: Path,
        *,
        language: str = "en",
        keywords: Optional[List[str]] = None,
        initial_prompt: Optional[str] = None,
    ) -> TranscriptionResult:
        """Transcribe audio using Deepgram Nova-2 API."""
        if not self.is_available():
            raise RuntimeError("DEEPGRAM_API_KEY is not set.")

        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        params: Dict[str, Any] = {
            "model": "nova-2",
            "language": language,
            "filler_words": "true",
            "smart_format": "true",
            "punctuate": "true",
            "utterances": "true",
        }
        if keywords:
            params["keywords"] = keywords[:50]

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "audio/wav",
        }

        with httpx.Client(timeout=60.0) as client:
            resp = client.post(self.api_url, params=params, headers=headers, content=audio_bytes)
            resp.raise_for_status()
            data = resp.json()

        results = data.get("results", {})
        channels = results.get("channels", [{}])
        channel = channels[0] if channels else {}
        alternatives = channel.get("alternatives", [{}])
        alt = alternatives[0] if alternatives else {}

        raw_words = alt.get("words", [])
        words: List[Word] = []
        for w in raw_words:
            raw_text = w.get("punctuated_word", w.get("word", ""))
            clean_text = re.sub(r"[^\w']", "", raw_text.strip().lower())
            words.append(
                Word(
                    text=clean_text,
                    start=round(float(w.get("start", 0.0)), 3),
                    end=round(float(w.get("end", 0.0)), 3),
                    confidence=round(float(w.get("confidence", 1.0)), 3),
                    source=WordSource.ASR,
                )
            )

        # Parse utterances into segments
        utterances = results.get("utterances", [])
        segments: List[Segment] = []
        if utterances:
            for u in utterances:
                u_words: List[Word] = []
                for w in u.get("words", []):
                    clean_text = re.sub(r"[^\w']", "", w.get("word", "").strip().lower())
                    u_words.append(
                        Word(
                            text=clean_text,
                            start=round(float(w.get("start", 0.0)), 3),
                            end=round(float(w.get("end", 0.0)), 3),
                            confidence=round(float(w.get("confidence", 1.0)), 3),
                            source=WordSource.ASR,
                        )
                    )
                segments.append(
                    Segment(
                        text=u.get("transcript", "").strip(),
                        start=round(float(u.get("start", 0.0)), 3),
                        end=round(float(u.get("end", 0.0)), 3),
                        words=u_words,
                        avg_logprob=0.0,
                        no_speech_prob=0.0,
                        language=language,
                    )
                )
        else:
            segments.append(
                Segment(
                    text=alt.get("transcript", "").strip(),
                    start=words[0].start if words else 0.0,
                    end=words[-1].end if words else 0.0,
                    words=words,
                    avg_logprob=0.0,
                    no_speech_prob=0.0,
                    language=language,
                )
            )

        duration = float(data.get("metadata", {}).get("duration", 0.0))
        if duration == 0.0 and words:
            duration = words[-1].end

        return TranscriptionResult(
            segments=segments,
            full_text=alt.get("transcript", "").strip(),
            words=words,
            duration_sec=round(duration, 2),
            provider_name=self.name,
            metadata=data.get("metadata", {}),
        )
