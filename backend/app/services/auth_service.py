from __future__ import annotations

import asyncio
from typing import Any

from supabase import Client

from app.core.exceptions import UnauthorizedError
from app.schemas.common import AuthenticatedUser


class AuthService:
    def __init__(self, client: Client) -> None:
        self.client = client

    async def validate_access_token(self, token: str) -> AuthenticatedUser:
        def operation() -> Any:
            import time
            import httpx
            import httpcore
            
            last_exc = None
            for attempt in range(3):
                try:
                    return self.client.auth.get_user(token)
                except Exception as e:
                    # Only retry on network/connection layer errors, not authorization errors
                    error_str = str(type(e).__name__)
                    if "Timeout" in error_str or "Protocol" in error_str or "Network" in error_str or "HTTPError" in error_str or "Connect" in error_str:
                        last_exc = e
                        if attempt < 2:
                            time.sleep(1.5)
                            continue
                    raise e
            if last_exc:
                raise last_exc

        try:
            response = await asyncio.to_thread(operation)
        except Exception as exc:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Supabase auth validation failed: {str(exc)}", exc_info=True)
            raise UnauthorizedError("Invalid Supabase access token") from exc

        user = getattr(response, "user", None)
        if user is None:
            raise UnauthorizedError("Supabase user lookup returned no user")

        return AuthenticatedUser(
            id=str(user.id),
            email=getattr(user, "email", None),
            role=(getattr(user, "user_metadata", {}) or {}).get("role"),
            full_name=(getattr(user, "user_metadata", {}) or {}).get("full_name") or (getattr(user, "user_metadata", {}) or {}).get("name"),
            raw_claims=getattr(user, "model_dump", lambda: {})(),
        )
