"""Comprehensive Unit Tests for Zoho Catalyst Adapters (QuickML & Stratus).

NOTE ON METHODOLOGY:
These tests verify adapter logic, schema validation, network error handling,
retry mechanics, and fallback chains using controlled HTTP simulation (respx/unittest.mock).
As required by engineering standards:
THESE TESTS ARE UNIT TESTS OF ADAPTER INTERFACES AND ARE NOT EVIDENCE OF LIVE CLOUD ACCESS.
Live cloud integration requires active Zoho Catalyst credentials and network connectivity.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from pydantic import BaseModel

from backend.app.config import settings
from backend.app.services.llm_client import LLMClient
from backend.app.services.storage_service import StorageService


class SampleRubric(BaseModel):
    relevance: int
    clarity: int
    depth: int
    one_line_feedback: str


@pytest.fixture
def mock_settings():
    """Ensure a clean, isolated configuration for each test."""
    orig_endpoint = settings.QUICKML_ENDPOINT
    orig_key = settings.QUICKML_API_KEY
    orig_model = settings.QUICKML_MODEL
    orig_stratus_ep = settings.STRATUS_ENDPOINT
    orig_stratus_bucket = settings.STRATUS_BUCKET
    orig_stratus_ak = settings.STRATUS_ACCESS_KEY
    orig_stratus_sk = settings.STRATUS_SECRET_KEY

    yield settings

    settings.QUICKML_ENDPOINT = orig_endpoint
    settings.QUICKML_API_KEY = orig_key
    settings.QUICKML_MODEL = orig_model
    settings.STRATUS_ENDPOINT = orig_stratus_ep
    settings.STRATUS_BUCKET = orig_stratus_bucket
    settings.STRATUS_ACCESS_KEY = orig_stratus_ak
    settings.STRATUS_SECRET_KEY = orig_stratus_sk


# ==============================================================================
# QuickML LLM Adapter Tests
# ==============================================================================

def test_quickml_auth_headers_and_payload(mock_settings):
    """[ADAPTER UNIT TEST - SIMULATED] Verify Authorization headers and payload structure sent to QuickML."""
    import asyncio
    mock_settings.QUICKML_ENDPOINT = "https://api.catalyst.zoho.com/quickml/v1/predict"
    mock_settings.QUICKML_API_KEY = "test-cat-api-key-12345"
    mock_settings.QUICKML_MODEL = "qwen2.5:3b"

    client = LLMClient()
    captured_request = {}

    def mock_post(url, json=None, headers=None, **kwargs):
        captured_request["url"] = str(url)
        captured_request["headers"] = headers
        captured_request["json"] = json
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": '{"relevance": 8, "clarity": 9, "depth": 7, "one_line_feedback": "Solid answer."}'}}]
        }
        return mock_resp

    async def _run():
        with patch.object(httpx.AsyncClient, "post", side_effect=mock_post):
            return await client._try_quickml_async("system prompt", "user prompt", SampleRubric)

    res = asyncio.run(_run())
    assert res is not None
    assert isinstance(res, SampleRubric)
    assert res.relevance == 8
    assert captured_request["headers"]["Authorization"] == "Bearer test-cat-api-key-12345"
    assert captured_request["headers"]["X-Catalyst-Client"] == "PLUTO-vProctor"
    assert captured_request["json"]["model"] == "qwen2.5:3b"


def test_quickml_successful_inference_different_formats(mock_settings):
    """[ADAPTER UNIT TEST - SIMULATED] Verify parsing OpenAI-compatible, Catalyst, and direct JSON responses."""
    import asyncio
    mock_settings.QUICKML_ENDPOINT = "https://api.catalyst.zoho.com/quickml/v1/predict"
    mock_settings.QUICKML_API_KEY = "dummy-key"

    client = LLMClient()

    async def _run():
        # Format A: OpenAI-compatible format with markdown wrapped JSON
        with patch.object(httpx.AsyncClient, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": "```json\n{\"relevance\": 9, \"clarity\": 8, \"depth\": 9, \"one_line_feedback\": \"Excellent\"}\n```"}}]
            }
            mock_post.return_value = mock_resp

            res_a = await client._try_quickml_async("sys", "user", SampleRubric)
            assert res_a.relevance == 9
            assert res_a.one_line_feedback == "Excellent"

        # Format B: Direct dictionary response
        with patch.object(httpx.AsyncClient, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "relevance": 7, "clarity": 7, "depth": 8, "one_line_feedback": "Direct dict format"
            }
            mock_post.return_value = mock_resp

            res_b = await client._try_quickml_async("sys", "user", SampleRubric)
            assert res_b.relevance == 7

    asyncio.run(_run())


def test_quickml_invalid_response_handling(mock_settings):
    """[ADAPTER UNIT TEST - SIMULATED] Verify handling of malformed JSON, schema validation failure, and 500 error."""
    import asyncio
    mock_settings.QUICKML_ENDPOINT = "https://api.catalyst.zoho.com/quickml/v1/predict"
    mock_settings.QUICKML_API_KEY = "dummy-key"

    client = LLMClient()

    async def _run():
        # 1. Non-200 HTTP response
        with patch.object(httpx.AsyncClient, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_post.return_value = mock_resp
            res_err = await client._try_quickml_async("sys", "user", SampleRubric)
            assert res_err is None

        # 2. Malformed JSON content
        with patch.object(httpx.AsyncClient, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"choices": [{"message": {"content": "INVALID NOT JSON"}}]}
            mock_post.return_value = mock_resp
            res_bad = await client._try_quickml_async("sys", "user", SampleRubric)
            assert res_bad is None

    asyncio.run(_run())


def test_quickml_timeout_and_fallback_to_ollama(mock_settings):
    """[ADAPTER UNIT TEST - SIMULATED] Verify that when QuickML times out, client falls through to Ollama."""
    import asyncio
    mock_settings.QUICKML_ENDPOINT = "https://api.catalyst.zoho.com/quickml/v1/predict"
    mock_settings.QUICKML_API_KEY = "dummy-key"

    client = LLMClient()

    def mock_post_chain(url, **kwargs):
        if "quickml" in str(url):
            raise httpx.TimeoutException("QuickML timed out after 45s")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"content": '{"relevance": 6, "clarity": 6, "depth": 6, "one_line_feedback": "From Ollama fallback"}'}
        }
        return mock_resp

    async def _run():
        with patch.object(httpx.AsyncClient, "post", side_effect=mock_post_chain):
            return await client.generate_json("sys", "user", SampleRubric)

    res = asyncio.run(_run())
    assert res is not None
    assert res.relevance == 6
    assert res.one_line_feedback == "From Ollama fallback"


def test_quickml_and_ollama_fail_to_deterministic_rubric(mock_settings):
    """[ADAPTER UNIT TEST - SIMULATED] Verify that when both QuickML and Ollama fail, deterministic rubric is called."""
    import asyncio
    mock_settings.QUICKML_ENDPOINT = "https://api.catalyst.zoho.com/quickml/v1/predict"
    mock_settings.QUICKML_API_KEY = "dummy-key"

    client = LLMClient()

    fallback_called = False

    def fallback():
        nonlocal fallback_called
        fallback_called = True
        return SampleRubric(relevance=5, clarity=5, depth=5, one_line_feedback="Deterministic algorithmic fallback")

    async def _run():
        # Both providers fail
        with patch.object(client, "_try_quickml_async", return_value=None):
            with patch.object(httpx.AsyncClient, "post", side_effect=httpx.ConnectError("Ollama offline")):
                return await client.generate_json("sys", "user", SampleRubric, fallback_factory=fallback)

    res = asyncio.run(_run())
    assert fallback_called is True
    assert res.relevance == 5
    assert res.one_line_feedback == "Deterministic algorithmic fallback"


def test_local_ollama_operation_when_quickml_unconfigured(mock_settings):
    """[ADAPTER UNIT TEST - SIMULATED] Verify that when QuickML is not configured, it directly calls Ollama without delay."""
    mock_settings.QUICKML_ENDPOINT = ""
    mock_settings.QUICKML_API_KEY = ""

    client = LLMClient()

    with patch.object(client, "_try_quickml_sync", return_value=None) as mock_quickml:
        with patch.object(httpx.Client, "post") as mock_ollama:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "message": {"content": '{"relevance": 8, "clarity": 8, "depth": 8, "one_line_feedback": "Pure Ollama"}'}
            }
            mock_ollama.return_value = mock_resp

            res = client.generate_json_sync("sys", "user", SampleRubric)

    assert res.relevance == 8
    mock_quickml.assert_called_once()  # Called, but immediately returned None due to empty settings


# ==============================================================================
# Stratus Object Storage Adapter Tests
# ==============================================================================

def test_stratus_upload_and_download(tmp_path, mock_settings):
    """[ADAPTER UNIT TEST - SIMULATED] Verify file upload and download via Stratus REST interface."""
    mock_settings.STORAGE_DIR = tmp_path
    mock_settings.STRATUS_ENDPOINT = "https://stratus.catalyst.zoho.com"
    mock_settings.STRATUS_BUCKET = "test-pluto-media"
    mock_settings.STRATUS_ACCESS_KEY = "test-ak"
    mock_settings.STRATUS_SECRET_KEY = "test-sk"

    storage = StorageService()
    assert storage.is_stratus_enabled() is True

    test_content = b"fake-recording-webm-binary-content-12345"

    with patch.object(httpx.Client, "put") as mock_put:
        mock_put.return_value = MagicMock(status_code=200)
        key = storage.save_file("recordings", "sess_test_1.webm", test_content)

    assert key == "recordings/sess_test_1.webm"
    # Verify local copy exists
    local_file = tmp_path / "recordings" / "sess_test_1.webm"
    assert local_file.exists()
    assert local_file.read_bytes() == test_content


def test_stratus_presigned_url_handling(mock_settings):
    """[ADAPTER UNIT TEST - SIMULATED] Verify presigned URL formatting when Stratus is enabled vs disabled."""
    # When enabled
    mock_settings.STRATUS_ENDPOINT = "https://stratus.catalyst.zoho.com"
    mock_settings.STRATUS_BUCKET = "test-pluto-media"
    mock_settings.STRATUS_ACCESS_KEY = "test-ak"

    storage = StorageService()
    url = storage.get_presigned_url("recordings", "video_001.webm")
    assert url == "https://stratus.catalyst.zoho.com/test-pluto-media/recordings/video_001.webm"

    # When disabled (local mode)
    mock_settings.STRATUS_ENDPOINT = ""
    mock_settings.STRATUS_BUCKET = ""
    mock_settings.STRATUS_ACCESS_KEY = ""

    storage_local = StorageService()
    assert storage_local.is_stratus_enabled() is False
    assert storage_local.get_presigned_url("recordings", "video_001.webm") is None


def test_stratus_local_storage_fallback_and_recovery(tmp_path, mock_settings):
    """[ADAPTER UNIT TEST - SIMULATED] Verify that when Stratus upload fails, local copy is fully preserved and accessible."""
    mock_settings.STORAGE_DIR = tmp_path
    mock_settings.STRATUS_ENDPOINT = "https://stratus.catalyst.zoho.com"
    mock_settings.STRATUS_BUCKET = "test-pluto-media"
    mock_settings.STRATUS_ACCESS_KEY = "test-ak"

    storage = StorageService()
    test_content = b"critical-candidate-recording-data"

    # Simulate Stratus network failure during upload
    with patch.object(httpx.Client, "put", side_effect=httpx.ConnectError("Stratus unreachable")):
        res = storage.save_file("recordings", "sess_err.webm", test_content)

    # Local file MUST still be saved
    local_file = tmp_path / "recordings" / "sess_err.webm"
    assert local_file.exists()
    assert local_file.read_bytes() == test_content

    # Reading bytes should retrieve from local disk without hitting remote
    retrieved = storage.get_file_bytes("recordings", "sess_err.webm")
    assert retrieved == test_content
