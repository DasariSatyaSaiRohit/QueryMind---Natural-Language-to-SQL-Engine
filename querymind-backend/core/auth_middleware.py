"""
core/auth_middleware.py
Session ownership verification dependency.

After JWT auth passes, confirms the session_id in the path/body
matches the session_id embedded in the JWT. Prevents cross-user
session access (user A querying user B's database session).
"""
from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, status

from core.auth import AuthenticatedUser, require_auth

logger = logging.getLogger(__name__)


async def verify_session_ownership(
    session_id: str,
    user: AuthenticatedUser = Depends(require_auth),
) -> AuthenticatedUser:
    """
    Confirm the session_id in the JWT matches the session_id being accessed.

    If they differ: raise 403 with error_type "session_ownership_violation".
    This prevents user A from querying user B's database session.

    Returns the authenticated user so downstream handlers can use it
    without calling require_auth again.
    """
    if user.session_id != session_id:
        logger.warning(
            "Session ownership violation: user=%s owns session=%s but tried to access session=%s",
            user.user_id,
            user.session_id,
            session_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_type": "session_ownership_violation",
                "message": (
                    "You are not authorized to access this session. "
                    "The requested session does not belong to your account."
                ),
            },
        )

    return user
