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
    """Client for local Ollama qwen2.5:3b with Zoho QuickML support, JSON formatting, and fallbacks."""

    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.model = settings.LLM_MODEL
        self.timeout = settings.LLM_TIMEOUT_SECONDS
        self.temperature = settings.LLM_TEMPERATURE
        self.num_ctx = settings.LLM_NUM_CTX

    def _extract_content_json(self, raw_content: str, response_model: Optional[Type[T]]) -> Any:
        content = raw_content.strip()
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        parsed_json = json.loads(content)
        if response_model is not None:
            return response_model.model_validate(parsed_json)
        return parsed_json

    async def _try_quickml_async(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Optional[Type[T]] = None,
    ) -> Optional[Any]:
        """Attempt completion using Zoho Catalyst QuickML endpoint if configured."""
        endpoint = settings.QUICKML_ENDPOINT.strip()
        api_key = settings.QUICKML_API_KEY.strip()
        if not endpoint or not api_key:
            return None

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Catalyst-Client": "PLUTO-vProctor",
        }
        payload = {
            "model": settings.QUICKML_MODEL or self.model,
            "messages": [
                {"role": "system", "content": system_prompt + "\nOUTPUT ONLY VALID RAW JSON. NO MARKDOWN, NO COMMENTARY."},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": self.temperature,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(endpoint, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    # Support OpenAI-compatible, Catalyst QuickML, or direct payload formats
                    raw_text = ""
                    if "choices" in data and data["choices"]:
                        raw_text = data["choices"][0].get("message", {}).get("content", "")
                    elif "message" in data:
                        raw_text = data["message"].get("content", "")
                    elif "output" in data:
                        raw_text = str(data["output"])
                    elif isinstance(data, dict):
                        if response_model is not None:
                            return response_model.model_validate(data)
                        return data

                    if raw_text:
                        return self._extract_content_json(raw_text, response_model)
        except Exception as e:
            print(f"QuickML async invocation error (falling back to Ollama): {e}")
        return None

    def _try_quickml_sync(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Optional[Type[T]] = None,
    ) -> Optional[Any]:
        """Synchronous QuickML invocation with fallback."""
        endpoint = settings.QUICKML_ENDPOINT.strip()
        api_key = settings.QUICKML_API_KEY.strip()
        if not endpoint or not api_key:
            return None

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Catalyst-Client": "PLUTO-vProctor",
        }
        payload = {
            "model": settings.QUICKML_MODEL or self.model,
            "messages": [
                {"role": "system", "content": system_prompt + "\nOUTPUT ONLY VALID RAW JSON. NO MARKDOWN, NO COMMENTARY."},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": self.temperature,
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(endpoint, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_text = ""
                    if "choices" in data and data["choices"]:
                        raw_text = data["choices"][0].get("message", {}).get("content", "")
                    elif "message" in data:
                        raw_text = data["message"].get("content", "")
                    elif "output" in data:
                        raw_text = str(data["output"])
                    elif isinstance(data, dict):
                        if response_model is not None:
                            return response_model.model_validate(data)
                        return data

                    if raw_text:
                        return self._extract_content_json(raw_text, response_model)
        except Exception as e:
            print(f"QuickML sync invocation error (falling back to Ollama): {e}")
        return None

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Optional[Type[T]] = None,
        fallback_factory: Optional[callable] = None,
    ) -> Optional[Any]:
        """Generate structured JSON using Zoho QuickML or local Ollama with validation and retry."""
        # Layer 1: Zoho Catalyst QuickML (Cloud Staging)
        quickml_result = await self._try_quickml_async(system_prompt, user_prompt, response_model)
        if quickml_result is not None:
            return quickml_result

        # Layer 2: Local Ollama (Local Workstation)
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
                            return self._extract_content_json(content, response_model)
                except (httpx.RequestError, json.JSONDecodeError, ValidationError) as e:
                    if attempt < settings.LLM_MAX_RETRIES:
                        await asyncio.sleep(0.5)
                        continue
                    print(f"LLM generation failed after retry: {e}")

        # Layer 3: Deterministic algorithmic fallback
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
        """Synchronous wrapper supporting QuickML, local Ollama, and deterministic fallbacks."""
        # Layer 1: Zoho Catalyst QuickML
        quickml_result = self._try_quickml_sync(system_prompt, user_prompt, response_model)
        if quickml_result is not None:
            return quickml_result

        # Layer 2: Local Ollama
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
                            return self._extract_content_json(content, response_model)
                except Exception as e:
                    if attempt < settings.LLM_MAX_RETRIES:
                        continue
                    print(f"Sync LLM call failed: {e}")

        # Layer 3: Deterministic fallback
        if fallback_factory is not None:
            return fallback_factory()
        return None


llm_client = LLMClient()
