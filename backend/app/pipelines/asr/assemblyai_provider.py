"""AssemblyAI hosted ASR provider for PLUTO vProctor.

Uses AssemblyAI API with disfluencies enabled (disfluencies=true)
and word-level timestamps.
"""
from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from backend.app.pipelines.asr import (
    ASRProvider, Segment, TranscriptionResult, Word, WordSource,
)


class AssemblyAIASRProvider(ASRProvider):
    """Hosted ASR provider using AssemblyAI API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ASSEMBLYAI_API_KEY", "")
        self.base_url = "https://api.assemblyai.com/v2"

    @property
    def name(self) -> str:
        return "assemblyai"

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
        """Transcribe audio using AssemblyAI API."""
        if not self.is_available():
            raise RuntimeError("ASSEMBLYAI_API_KEY is not set.")

        headers = {
            "authorization": self.api_key,
        }

        with httpx.Client(timeout=120.0) as client:
            # 1. Upload audio file
            with open(audio_path, "rb") as f:
                upload_resp = client.post(
                    f"{self.base_url}/upload",
                    headers=headers,
                    content=f.read(),
                )
                upload_resp.raise_for_status()
                upload_url = upload_resp.json().get("upload_url")

            # 2. Submit transcription job
            payload: Dict[str, Any] = {
                "audio_url": upload_url,
                "disfluencies": True,
                "language_code": language,
            }
            if keywords:
                payload["word_boost"] = keywords[:50]
                payload["boost_param"] = "high"

            transcript_resp = client.post(
                f"{self.base_url}/transcript",
                headers={**headers, "content-type": "application/json"},
                json=payload,
            )
            transcript_resp.raise_for_status()
            transcript_id = transcript_resp.json().get("id")

            # 3. Poll for completion
            polling_url = f"{self.base_url}/transcript/{transcript_id}"
            max_wait_sec = 180
            start_poll = time.time()
            data = {}

            while time.time() - start_poll < max_wait_sec:
                poll_resp = client.get(polling_url, headers=headers)
                poll_resp.raise_for_status()
                data = poll_resp.json()
                status = data.get("status")
                if status == "completed":
                    break
                elif status == "error":
                    raise RuntimeError(f"AssemblyAI transcription failed: {data.get('error')}")
                time.sleep(2.0)

            if data.get("status") != "completed":
                raise TimeoutError("AssemblyAI transcription timed out.")

        raw_words = data.get("words", [])
        words: List[Word] = []
        for w in raw_words:
            raw_text = w.get("text", "")
            clean_text = re.sub(r"[^\w']", "", raw_text.strip().lower())
            start_sec = round(float(w.get("start", 0)) / 1000.0, 3)
            end_sec = round(float(w.get("end", 0)) / 1000.0, 3)
            conf = round(float(w.get("confidence", 1.0)), 3)
            words.append(
                Word(
                    text=clean_text,
                    start=start_sec,
                    end=end_sec,
                    confidence=conf,
                    source=WordSource.ASR,
                )
            )

        duration = float(data.get("audio_duration", 0.0))
        if duration == 0.0 and words:
            duration = words[-1].end

        segment = Segment(
            text=data.get("text", "").strip(),
            start=words[0].start if words else 0.0,
            end=words[-1].end if words else 0.0,
            words=words,
            avg_logprob=0.0,
            no_speech_prob=0.0,
            language=language,
        )

        return TranscriptionResult(
            segments=[segment],
            full_text=data.get("text", "").strip(),
            words=words,
            duration_sec=round(duration, 2),
            provider_name=self.name,
            metadata={"transcript_id": transcript_id},
        )
