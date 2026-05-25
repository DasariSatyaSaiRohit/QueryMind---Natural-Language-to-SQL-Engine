"""
core/auth.py
JWT verification dependency for FastAPI.
The NestJS gateway signs tokens; this backend only verifies them.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt, ExpiredSignatureError
from pydantic import BaseModel

from core.config import get_settings
from core.context import set_session_id

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


class AuthenticatedUser(BaseModel):
    user_id: str
    session_id: str


def _decode_token(token: str) -> dict:
    """
    Decode and verify a JWT token.
    Raises HTTPException on any failure.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=["HS256"],
        )
        return payload
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_type": "token_expired",
                "message": "The JWT token has expired. Please re-authenticate.",
            },
        )
    except JWTError as exc:
        logger.warning("JWT decode failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_type": "invalid_token",
                "message": "The JWT token is invalid.",
            },
        )


async def require_auth(token: Optional[str] = Depends(oauth2_scheme)) -> AuthenticatedUser:
    """
    Verify JWT signed by the NestJS gateway.

    Steps:
      1. If token is None: raise 401 with error_type "missing_token".
      2. Decode using settings.JWT_SECRET, algorithm HS256.
      3. Check exp claim — raise 401 "token_expired" if expired.
      4. Extract sub (user_id) and session_id from payload.
      5. Set session_id_var via context.set_session_id(session_id).
      6. Return AuthenticatedUser(user_id=sub, session_id=session_id).
    On JWTError: raise 401 with error_type "invalid_token".
    Never raise 500 from this function.
    """
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_type": "missing_token",
                "message": "Authorization header with Bearer token is required.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = _decode_token(token)

    user_id = payload.get("sub")
    session_id = payload.get("session_id")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_type": "invalid_token",
                "message": "Token payload missing 'sub' (user_id) claim.",
            },
        )

    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_type": "invalid_token",
                "message": "Token payload missing 'session_id' claim.",
            },
        )

    set_session_id(session_id)

    return AuthenticatedUser(user_id=user_id, session_id=session_id)


async def optional_auth(
    token: Optional[str] = Depends(oauth2_scheme),
) -> Optional[AuthenticatedUser]:
    """
    Same as require_auth but returns None instead of raising on missing token.
    Used for the health endpoint and public routes.
    """
    if token is None:
        return None

    try:
        payload = _decode_token(token)
    except HTTPException:
        return None

    user_id = payload.get("sub")
    session_id = payload.get("session_id")

    if not user_id or not session_id:
        return None

    set_session_id(session_id)
    return AuthenticatedUser(user_id=user_id, session_id=session_id)
