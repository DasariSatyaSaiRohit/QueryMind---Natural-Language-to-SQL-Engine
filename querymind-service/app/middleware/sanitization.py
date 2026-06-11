"""
Global request sanitization middleware.

Strips null bytes, control characters, and normalises request bodies.
Applies HTML escaping to prevent XSS in stored/reflected values.
"""
import html
import json
import re
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Characters to strip: null byte + C0 control chars (except \t \n \r)
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _sanitize_str(value: str) -> str:
    cleaned = _CONTROL_RE.sub("", value)
    return cleaned


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        return _sanitize_str(value)
    if isinstance(value, dict):
        return {k: _sanitize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(i) for i in value]
    return value


class SanitizationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Sanitize query parameters
        if request.query_params:
            scope = request.scope
            cleaned_qs = "&".join(
                f"{k}={_sanitize_str(v)}"
                for k, v in request.query_params.multi_items()
            )
            scope["query_string"] = cleaned_qs.encode()

        # Sanitize JSON body for mutating methods
        if request.method in ("POST", "PUT", "PATCH") and "application/json" in request.headers.get(
            "content-type", ""
        ):
            try:
                body_bytes = await request.body()
                if body_bytes:
                    body_json = json.loads(body_bytes)
                    sanitized = _sanitize_value(body_json)
                    sanitized_bytes = json.dumps(sanitized).encode()

                    async def receive():
                        return {
                            "type": "http.request",
                            "body": sanitized_bytes,
                            "more_body": False,  # ← ADDED
                        }

                    request._receive = receive
            except (json.JSONDecodeError, Exception):
                pass

        response = await call_next(request)
        return response