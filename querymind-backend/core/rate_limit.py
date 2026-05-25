"""
core/rate_limit.py
Rate limiting using slowapi, keyed by JWT user_id (not IP).

Rate limit tiers (apply as decorators on route handlers):
  @limiter.limit("60/minute")   — standard endpoints
  @limiter.limit("10/minute")   — query generation (Claude calls are expensive)
  @limiter.limit("5/minute")    — session connect (DB connections are expensive)
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import Request
from jose import jwt, JWTError
from slowapi import Limiter

from core.config import settings

logger = logging.getLogger(__name__)


def get_user_id_key(request: Request) -> str:
    """
    Extract user_id from the JWT token in the Authorization header.
    Falls back to remote address if token is absent or invalid.
    Used as the rate limit key — limits are per user, not per IP.
    """
    auth_header: Optional[str] = request.headers.get("Authorization")

    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer "):]
        try:
            settings = settings()
            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=["HS256"],
            )
            user_id: Optional[str] = payload.get("sub")
            if user_id:
                return f"user:{user_id}"
        except JWTError:
            # Invalid / expired token — fall through to IP-based key
            logger.debug(
                "rate_limit: JWT decode failed for key extraction, falling back to IP"
            )

    # Fallback: use client IP (handles unauthenticated requests)
    client = request.client
    remote_addr = client.host if client else "unknown"
    return f"ip:{remote_addr}"


# Module-level singleton used by all routers via Depends or decorator
limiter = Limiter(key_func=get_user_id_key)
