from __future__ import annotations

import base64
import hashlib
import hmac
import os
import struct
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import jwt
from cachetools import TTLCache
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.settings import Settings, get_settings


bearer = HTTPBearer(auto_error=False)

_token_cache = TTLCache(maxsize=1000, ttl=300)


@dataclass
class CurrentUser:
    id: str
    email: str
    metadata: dict[str, Any]


@dataclass
class AdminUser:
    id: str
    email: str
    role: str
    institution_id: str | None = None
    department_id: str | None = None
    token_version: int = 0
    issued_at: int = 0


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return f"pbkdf2_sha256${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, salt_b64, digest_b64 = stored_hash.split("$", 2)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def create_admin_token(settings: Settings, payload: dict[str, Any]) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        **payload,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=12)).timestamp()),
        "iss": "celtm-phase1",
    }
    return jwt.encode(claims, settings.resolved_jwt_secret, algorithm="HS256")


def decode_admin_token(settings: Settings, token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.resolved_jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired admin token") from exc


async def validate_supabase_token(settings: Settings, token: str) -> CurrentUser:
    if not settings.supabase_url or not settings.supabase_api_key:
        raise HTTPException(
            status_code=500,
            detail="Supabase is not configured for student authentication",
        )

    cached_user = _token_cache.get(token)
    if cached_user:
        return cached_user

    url = settings.supabase_url.rstrip("/") + "/auth/v1/user"
    headers = {
        "Authorization": f"Bearer {token}",
        "apikey": settings.supabase_api_key,
    }
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=401, detail="Unable to verify student session") from exc

    if response.status_code >= 400:
        raise HTTPException(status_code=401, detail="Invalid student session")

    data = response.json()
    metadata = data.get("user_metadata") if isinstance(data.get("user_metadata"), dict) else {}
    email = data.get("email") or metadata.get("email") or ""
    user = CurrentUser(id=data["id"], email=email, metadata=metadata)
    _token_cache[token] = user
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Bearer token is required")
    return await validate_supabase_token(settings, credentials.credentials)


async def get_admin_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    settings: Settings = Depends(get_settings),
) -> AdminUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Admin bearer token is required")
    claims = decode_admin_token(settings, credentials.credentials)
    return AdminUser(
        id=str(claims.get("sub", "")),
        email=str(claims.get("email", "")),
        role=str(claims.get("role", "")),
        institution_id=claims.get("institution_id"),
        department_id=claims.get("department_id"),
        token_version=int(claims.get("token_version") or 0),
        issued_at=int(claims.get("iat") or 0),
    )


def require_super_admin(admin: AdminUser) -> None:
    if admin.role != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")


def verify_gateway_code(
    x_gateway_code: str | None = Header(default=None, alias="X-Gateway-Code"),
    settings: Settings = Depends(get_settings),
) -> None:
    if settings.admin_gateway_code and x_gateway_code and x_gateway_code != settings.admin_gateway_code:
        raise HTTPException(status_code=403, detail="Invalid gateway code")


def _totp_at(secret: str, counter: int, digits: int = 6) -> str:
    normalized = "".join(ch for ch in secret.strip().replace(" ", "").upper() if ch.isalnum())
    padding = "=" * ((8 - len(normalized) % 8) % 8)
    key = base64.b32decode(normalized + padding, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10 ** digits)).zfill(digits)


def verify_totp_code(secret: str, code: str | None, window: int = 1) -> bool:
    if not secret or not code:
        return False
    cleaned = "".join(ch for ch in str(code) if ch.isdigit())
    if len(cleaned) != 6:
        return False
    counter = int(time.time() // 30)
    try:
        return any(hmac.compare_digest(_totp_at(secret, counter + offset), cleaned) for offset in range(-window, window + 1))
    except Exception:
        return False


def generate_totp_secret() -> str:
    return base64.b32encode(os.urandom(20)).decode("ascii").rstrip("=")


def totp_uri(secret: str, account_name: str, issuer: str = "CELTM") -> str:
    from urllib.parse import quote

    normalized_secret = "".join(ch for ch in secret.strip().replace(" ", "").upper() if ch.isalnum())
    label = quote(f"{issuer}:{account_name}")
    issuer_q = quote(issuer)
    return f"otpauth://totp/{label}?secret={normalized_secret}&issuer={issuer_q}&algorithm=SHA1&digits=6&period=30"
