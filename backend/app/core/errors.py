"""Unified API error envelope and exception handlers preserving FastAPI 'detail'."""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("pluto.errors")


class AppError(HTTPException):
    """Structured domain HTTP exception carrying an explicit machine-readable code."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        super().__init__(status_code=status_code, detail=message, headers=headers)
        self.code = code
        self.details = details


def _resolve_request_id(request: Request) -> str:
    req_id = getattr(request.state, "request_id", None)
    if req_id:
        return str(req_id)
    header_id = request.headers.get("X-Request-ID")
    if header_id:
        return header_id
    return str(uuid.uuid4())[:8]


def build_error_payload(
    *,
    code: str,
    message: str,
    request_id: str,
    details: Optional[Any] = None,
    detail: Optional[Any] = None,
) -> Dict[str, Any]:
    """Build backwards-compatible payload preserving top-level 'detail' and structured 'error'."""
    return {
        "detail": detail if detail is not None else message,
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
            "details": details,
        },
    }


def _sanitized_validation_details(exc: RequestValidationError) -> List[Dict[str, Any]]:
    sanitized: List[Dict[str, Any]] = []
    for err in exc.errors():
        sanitized.append({
            "loc": list(err.get("loc", ())),
            "msg": str(err.get("msg", "Invalid value")),
            "type": str(err.get("type", "value_error")),
        })
    return sanitized


def register_exception_handlers(app: FastAPI) -> None:
    """Attach standardized JSON exception handlers for HTTP, validation, and 500 errors."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        req_id = _resolve_request_id(request)
        payload = build_error_payload(
            code=exc.code,
            message=str(exc.detail),
            request_id=req_id,
            details=exc.details,
        )
        headers = dict(exc.headers or {})
        headers.setdefault("X-Request-ID", req_id)
        return JSONResponse(status_code=exc.status_code, content=payload, headers=headers)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        req_id = _resolve_request_id(request)
        code = getattr(exc, "code", None) or f"HTTP_{exc.status_code}"
        msg = exc.detail if isinstance(exc.detail, str) else "Request failed"
        payload = build_error_payload(
            code=code,
            message=msg,
            request_id=req_id,
            details=None if isinstance(exc.detail, str) else exc.detail,
            detail=exc.detail,
        )
        headers = dict(getattr(exc, "headers", None) or {})
        headers.setdefault("X-Request-ID", req_id)
        return JSONResponse(status_code=exc.status_code, content=payload, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        req_id = _resolve_request_id(request)
        details = _sanitized_validation_details(exc)
        payload = build_error_payload(
            code="VALIDATION_ERROR",
            message="Request validation failed",
            request_id=req_id,
            details=details,
            detail=details,
        )
        return JSONResponse(
            status_code=422,
            content=payload,
            headers={"X-Request-ID": req_id},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        req_id = _resolve_request_id(request)
        logger.error("Unhandled exception [Req:%s] %s %s: %s", req_id, request.method, request.url.path, exc, exc_info=True)
        payload = build_error_payload(
            code="INTERNAL_ERROR",
            message="An internal server error occurred.",
            request_id=req_id,
            details=None,
        )
        return JSONResponse(
            status_code=500,
            content=payload,
            headers={"X-Request-ID": req_id},
        )

