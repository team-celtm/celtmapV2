from __future__ import annotations

import jwt
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config.settings import Settings
from app.core.exceptions import UnauthorizedError


class AdminAuthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.secret_key = settings.supabase_secret_key or "admin-secret-key"
        self.algorithm = "HS256"

    async def login(self, username: str, password: str) -> dict[str, Any]:
        """
        Validates admin credentials and returns a token.
        """
        if username != self.settings.admin_user or password != self.settings.admin_pass:
            raise UnauthorizedError("Invalid admin credentials")

        payload = {
            "sub": "admin",
            "role": "admin",
            "exp": datetime.now(timezone.utc) + timedelta(hours=8),
            "iat": datetime.now(timezone.utc),
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": "admin",
                "role": "admin",
                "username": username
            }
        }

    async def validate_token(self, token: str) -> bool:
        """
        Validates the admin JWT token.
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload.get("role") == "admin"
        except (jwt.PyJWTError, KeyError):
            return False
