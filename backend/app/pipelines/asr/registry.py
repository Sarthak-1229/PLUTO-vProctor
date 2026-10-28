"""ASR provider registry and factory for PLUTO vProctor.

Selects the best available provider based on environment variables and config.
"""
from __future__ import annotations

import os
from typing import Optional

from backend.app.pipelines.asr import ASRProvider
from backend.app.pipelines.asr.faster_whisper_provider import FasterWhisperASRProvider

# Lazy-loaded singleton instances
_provider_cache: dict[str, ASRProvider] = {}


def get_asr_provider(preferred: Optional[str] = None) -> ASRProvider:
    """Return the best available ASR provider.

    Selection priority:
    1. Explicit `preferred` argument.
    2. `ASR_PROVIDER` environment variable.
    3. Auto-detect: hosted provider if API key is present, else local fallback.
    """
    provider_name = preferred or os.environ.get("ASR_PROVIDER", "auto")

    if provider_name in _provider_cache:
        return _provider_cache[provider_name]

    if provider_name == "auto":
        # Try hosted providers first if keys are present
        if os.environ.get("DEEPGRAM_API_KEY"):
            provider_name = "deepgram"
        elif os.environ.get("ASSEMBLYAI_API_KEY"):
            provider_name = "assemblyai"
        else:
            provider_name = "faster_whisper"

    if provider_name == "deepgram":
        try:
            from backend.app.pipelines.asr.deepgram_provider import DeepgramASRProvider
            provider = DeepgramASRProvider()
            if provider.is_available():
                _provider_cache[provider_name] = provider
                return provider
        except ImportError:
            pass
        # Fallback
        provider_name = "faster_whisper"

    if provider_name == "assemblyai":
        try:
            from backend.app.pipelines.asr.assemblyai_provider import AssemblyAIASRProvider
            provider = AssemblyAIASRProvider()
            if provider.is_available():
                _provider_cache[provider_name] = provider
                return provider
        except ImportError:
            pass
        # Fallback
        provider_name = "faster_whisper"

    # Default: local faster-whisper
    if "faster_whisper" not in _provider_cache:
        _provider_cache["faster_whisper"] = FasterWhisperASRProvider()
    return _provider_cache["faster_whisper"]

