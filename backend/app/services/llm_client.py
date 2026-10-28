"""Local offline LLM client via Ollama (qwen2.5:3b) with GPU concurrency locking and fallback.

Strictly adheres to GEMINI.md non-negotiable rules:
1. Pure local offline inference via Ollama.
2. JSON-only prompts with Pydantic validation.
3. Timeout protection, 1 retry, and deterministic fallback.
4. GPU lock preventing concurrent VRAM contention.
"""
from __future__ import annotations

import asyncio
import json
import threading
from typing import Any, Dict, Optional, Type, TypeVar
import httpx
from pydantic import BaseModel, ValidationError

from backend.app.config import settings

T = TypeVar("T", bound=BaseModel)

# Global GPU lock to prevent multiple GPU models from loading concurrently
_GPU_LOCK = asyncio.Lock()
_THREAD_GPU_LOCK = threading.Lock()


class LLMClient:
    """Client for local Ollama qwen2.5:3b with JSON formatting and fallbacks."""

    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.model = settings.LLM_MODEL
        self.timeout = settings.LLM_TIMEOUT_SECONDS
        self.temperature = settings.LLM_TEMPERATURE
        self.num_ctx = settings.LLM_NUM_CTX

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Optional[Type[T]] = None,
        fallback_factory: Optional[callable] = None,
    ) -> Optional[Any]:
        """Generate structured JSON using local Ollama model with validation and retry."""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt + "\nOUTPUT ONLY VALID RAW JSON. NO MARKDOWN, NO COMMENTARY."},
                {"role": "user", "content": user_prompt},
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.num_ctx,
            },
        }

        async with _GPU_LOCK:
            for attempt in range(settings.LLM_MAX_RETRIES + 1):
                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                        if resp.status_code == 200:
                            data = resp.json()
                            content = data.get("message", {}).get("content", "").strip()
                            # Clean potential markdown wrapping
                            if content.startswith("```json"):
                                content = content[7:]
                            if content.endswith("```"):
                                content = content[:-3]
                            content = content.strip()

                            parsed_json = json.loads(content)
                            if response_model is not None:
                                return response_model.model_validate(parsed_json)
                            return parsed_json
                except (httpx.RequestError, json.JSONDecodeError, ValidationError) as e:
                    if attempt < settings.LLM_MAX_RETRIES:
                        await asyncio.sleep(0.5)
                        continue
                    print(f"LLM generation failed after retry: {e}")

        # Deterministic fallback
        if fallback_factory is not None:
            return fallback_factory()
        return None

    def generate_json_sync(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Optional[Type[T]] = None,
        fallback_factory: Optional[callable] = None,
    ) -> Optional[Any]:
        """Synchronous wrapper for offline scripts and worker processes."""
        with _THREAD_GPU_LOCK:
            for attempt in range(settings.LLM_MAX_RETRIES + 1):
                try:
                    with httpx.Client(timeout=self.timeout) as client:
                        resp = client.post(
                            f"{self.base_url}/api/chat",
                            json={
                                "model": self.model,
                                "messages": [
                                    {"role": "system", "content": system_prompt + "\nOUTPUT ONLY VALID RAW JSON. NO MARKDOWN."},
                                    {"role": "user", "content": user_prompt},
                                ],
                                "format": "json",
                                "stream": False,
                                "options": {
                                    "temperature": self.temperature,
                                    "num_ctx": self.num_ctx,
                                },
                            },
                        )
                        if resp.status_code == 200:
                            content = resp.json().get("message", {}).get("content", "").strip()
                            if content.startswith("```json"):
                                content = content[7:]
                            if content.endswith("```"):
                                content = content[:-3]
                            parsed_json = json.loads(content.strip())
                            if response_model is not None:
                                return response_model.model_validate(parsed_json)
                            return parsed_json
                except Exception as e:
                    if attempt < settings.LLM_MAX_RETRIES:
                        continue
                    print(f"Sync LLM call failed: {e}")

        if fallback_factory is not None:
            return fallback_factory()
        return None


llm_client = LLMClient()
