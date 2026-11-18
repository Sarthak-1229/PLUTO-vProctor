"""Zoho Catalyst Zia AI integration for cloud ML resume parsing, answer analysis, and OCR.

Uses the native `zcatalyst_sdk` Zia component (`catalyst_app.zia()`) directly inside
Zoho Catalyst AppSail with zero manual API keys:
- Zia Text Analytics (Sentiment Analysis + Keyword Extraction + NER) for candidate
  spoken answers and resumes
- Zia OCR fallback for scanned image-only PDF resumes
Gracefully no-ops in local offline workstation mode and pytest.
"""
from __future__ import annotations

import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.services.catalyst_context import get_catalyst_app

logger = logging.getLogger("pluto.zia")

_METRICS_LOCK = threading.Lock()
_ZIA_METRICS: Dict[str, Any] = {
    "calls_total": 0,
    "calls_succeeded": 0,
    "calls_failed": 0,
    "last_operation": None,
    "last_error": None,
}


def get_zia_metrics() -> Dict[str, Any]:
    """Return safe operational telemetry for Zoho Zia AI usage."""
    with _METRICS_LOCK:
        return dict(_ZIA_METRICS)


def _record_zia_result(operation: str, ok: bool, error: Optional[str] = None) -> None:
    with _METRICS_LOCK:
        _ZIA_METRICS["calls_total"] += 1
        _ZIA_METRICS["last_operation"] = operation
        if ok:
            _ZIA_METRICS["calls_succeeded"] += 1
            _ZIA_METRICS["last_error"] = None
        else:
            _ZIA_METRICS["calls_failed"] += 1
            _ZIA_METRICS["last_error"] = (error or "")[:200]


def _parse_keywords(raw: Any) -> List[str]:
    found: List[str] = []
    if isinstance(raw, dict):
        for k in ("keywords", "keyphrases", "general_entities"):
            vals = raw.get(k)
            if isinstance(vals, list):
                for item in vals:
                    if isinstance(item, str) and item.strip():
                        found.append(item.strip())
                    elif isinstance(item, dict):
                        val = item.get("keyword") or item.get("token") or item.get("value")
                        if val:
                            found.append(str(val).strip())
    elif isinstance(raw, list):
        for entry in raw:
            found.extend(_parse_keywords(entry))
    # Deduplicate preserving order
    return list(dict.fromkeys(found))


def _parse_sentiment(raw: Any) -> Dict[str, Any]:
    out = {"sentiment": "Neutral", "confidence": 0.5}
    if isinstance(raw, list) and raw:
        raw = raw[0]
    if isinstance(raw, dict):
        doc_sent = raw.get("document_sentiment") or raw.get("sentiment")
        if isinstance(doc_sent, str) and doc_sent.strip():
            out["sentiment"] = doc_sent.strip()
        overall = raw.get("overall_score") or raw.get("confidence_score") or raw.get("confidence_scores")
        if isinstance(overall, (int, float)):
            out["confidence"] = round(float(overall), 3)
        elif isinstance(overall, dict):
            key = out["sentiment"].lower()
            for k, v in overall.items():
                if k.lower() == key and isinstance(v, (int, float)):
                    out["confidence"] = round(float(v), 3)
                    break
    return out


def _parse_ner(raw: Any) -> Dict[str, List[str]]:
    persons: List[str] = []
    orgs: List[str] = []
    locations: List[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                _walk(item)
        elif isinstance(node, dict):
            tag = str(node.get("ner_tag") or node.get("type") or "").lower()
            tok = str(node.get("token") or node.get("value") or "").strip()
            if tok:
                if "person" in tag:
                    persons.append(tok)
                elif "org" in tag:
                    orgs.append(tok)
                elif "loc" in tag or "city" in tag:
                    locations.append(tok)
            for v in node.values():
                if isinstance(v, (list, dict)):
                    _walk(v)

    _walk(raw)
    return {
        "persons": list(dict.fromkeys(persons)),
        "organizations": list(dict.fromkeys(orgs)),
        "locations": list(dict.fromkeys(locations)),
    }


def _unwrap_zia_doc(raw: Any) -> Dict[str, Any]:
    """Unwrap Zia response list / nested 'response' envelope into a flat document dict."""
    node = raw
    if isinstance(node, list) and node:
        node = node[0]
    if isinstance(node, dict) and isinstance(node.get("response"), dict):
        node = node["response"]
    if isinstance(node, list) and node:
        node = node[0]
    return node if isinstance(node, dict) else {}


def analyze_answer_with_zia(
    transcript: str,
    expected_keywords: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Run Zoho Catalyst Zia Text Analytics (sentiment + keywords) on a candidate answer."""
    clean = (transcript or "").strip()
    if len(clean) < 12:
        return None

    catalyst_app = get_catalyst_app(scope="admin")
    if catalyst_app is None:
        return None

    snippet = clean[:1500]
    kw_list = [k.strip() for k in (expected_keywords or []) if k and k.strip()][:10]
    try:
        zia = catalyst_app.zia()
        raw = zia.get_text_analytics([snippet], keywords=kw_list or None)
        doc = _unwrap_zia_doc(raw)
        sent_raw = doc.get("sentiment_prediction") or doc
        kw_raw = doc.get("keyword_extractor") or doc
        sent = _parse_sentiment(sent_raw)
        keywords = _parse_keywords(kw_raw)[:15]
        _record_zia_result("text_analytics", True)
        return {
            "provider": "zoho_zia",
            "sentiment": sent["sentiment"],
            "confidence": sent["confidence"],
            "keywords": keywords,
        }
    except Exception as exc:
        _record_zia_result("text_analytics", False, str(exc))
        logger.debug("Zoho Zia text analytics skipped/failed: %s", exc)
        return None


def analyze_resume_with_zia(raw_text: str) -> Optional[Dict[str, Any]]:
    """Run Zoho Catalyst Zia Keyword Extraction & NER on parsed resume text."""
    clean = (raw_text or "").strip()
    if len(clean) < 25:
        return None

    catalyst_app = get_catalyst_app(scope="admin")
    if catalyst_app is None:
        return None

    snippet = clean[:1500]
    try:
        zia = catalyst_app.zia()
        raw = zia.get_text_analytics([snippet])
        doc = _unwrap_zia_doc(raw)
        kw_raw = doc.get("keyword_extractor") or doc
        ner_raw = doc.get("ner") or doc
        keywords = _parse_keywords(kw_raw)[:20]
        ner = _parse_ner(ner_raw)
        _record_zia_result("resume_analytics", True)
        return {
            "provider": "zoho_zia",
            "keywords": keywords,
            "persons": ner["persons"][:5],
            "organizations": ner["organizations"][:10],
            "locations": ner["locations"][:5],
        }
    except Exception as exc:
        _record_zia_result("resume_analytics", False, str(exc))
        logger.debug("Zoho Zia resume analytics skipped/failed: %s", exc)
        return None


def ocr_file_with_zia(file_bytes: bytes, suffix: str = ".pdf") -> str:
    """Use Zoho Catalyst Zia OCR as fallback when a scanned PDF/image yields no text."""
    if not file_bytes or len(file_bytes) > 10 * 1024 * 1024:
        return ""

    catalyst_app = get_catalyst_app(scope="admin")
    if catalyst_app is None:
        return ""

    tmp_fd, tmp_name = tempfile.mkstemp(prefix="pluto_zia_ocr_", suffix=suffix or ".pdf")
    os.close(tmp_fd)
    tmp_path = Path(tmp_name)
    try:
        tmp_path.write_bytes(file_bytes)
        with open(tmp_path, "rb") as fh:
            data = catalyst_app.zia().extract_optical_characters(fh)
        text = ""
        if isinstance(data, dict):
            text = str(data.get("text") or "").strip()
        _record_zia_result("ocr", bool(text))
        return text
    except Exception as exc:
        _record_zia_result("ocr", False, str(exc))
        logger.debug("Zoho Zia OCR fallback skipped/failed: %s", exc)
        return ""
    finally:
        tmp_path.unlink(missing_ok=True)
