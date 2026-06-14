from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.database import new_id
from app.settings import Settings


@dataclass(frozen=True)
class StoredUpload:
    bucket_name: str
    storage_path: str
    reference: str
    signed_url: str | None = None


def _safe_file_name(filename: str | None) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", filename or "upload.bin").strip(".-")
    return safe or "upload.bin"


def _service_key(settings: Settings) -> str:
    return settings.supabase_service_role_key or settings.supabase_secret_key


def storage_reference(bucket: str, path: str) -> str:
    return f"supabase://{bucket}/{path.lstrip('/')}"


def parse_storage_reference(value: str | None) -> tuple[str, str] | None:
    raw = str(value or "").strip()
    if not raw.startswith("supabase://"):
        return None
    rest = raw.removeprefix("supabase://")
    if "/" not in rest:
        return None
    bucket, path = rest.split("/", 1)
    if not bucket or not path:
        return None
    return bucket, path


def _storage_headers(settings: Settings, content_type: str | None = None) -> dict[str, str]:
    key = _service_key(settings)
    if not settings.supabase_url or not key:
        raise RuntimeError("Supabase private storage is not configured")
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


async def ensure_private_bucket(settings: Settings) -> None:
    if settings.effective_storage_backend != "supabase" or not settings.supabase_storage_create_bucket:
        return
    base_url = settings.supabase_url.rstrip("/")
    bucket = settings.supabase_storage_bucket.strip()
    if not base_url or not bucket:
        return
    async with httpx.AsyncClient(timeout=12) as client:
        response = await client.post(
            f"{base_url}/storage/v1/bucket",
            headers=_storage_headers(settings, "application/json"),
            json={"name": bucket, "public": False},
        )
    if response.status_code in {200, 201, 409}:
        return
    if response.status_code == 400 and "already" in response.text.lower():
        return
    raise RuntimeError(f"Could not ensure Supabase storage bucket '{bucket}': {response.text[:200]}")


async def store_upload(
    settings: Settings,
    user_id: str,
    filename: str | None,
    content: bytes,
    content_type: str | None,
    category: str,
) -> StoredUpload:
    safe_name = _safe_file_name(filename)
    clean_category = re.sub(r"[^A-Za-z0-9_-]+", "-", category or "uploads").strip("-") or "uploads"
    object_path = f"{user_id}/{clean_category}/{new_id('file')}-{safe_name}"

    if settings.effective_storage_backend == "supabase":
        bucket = settings.supabase_storage_bucket.strip()
        base_url = settings.supabase_url.rstrip("/")
        upload_url = f"{base_url}/storage/v1/object/{bucket}/{object_path}"
        headers = _storage_headers(settings, content_type or "application/octet-stream")
        headers["x-upsert"] = "false"
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(upload_url, headers=headers, content=content)
        if response.status_code not in {200, 201}:
            raise RuntimeError(f"Could not store private upload: {response.text[:200]}")
        return StoredUpload(
            bucket_name=bucket,
            storage_path=object_path,
            reference=storage_reference(bucket, object_path),
            signed_url=sign_storage_url(settings, bucket, object_path),
        )

    folder = settings.upload_dir / user_id / clean_category
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{new_id('file')}-{safe_name}"
    path.write_bytes(content)
    storage_path = str(path.relative_to(settings.upload_dir)).replace("\\", "/")
    return StoredUpload(
        bucket_name="local-phase1",
        storage_path=storage_path,
        reference=f"/files/{storage_path}",
        signed_url=f"/files/{storage_path}",
    )


def sign_storage_url(settings: Settings, bucket: str | None, path: str | None) -> str | None:
    clean_bucket = str(bucket or "").strip()
    clean_path = str(path or "").strip().lstrip("/")
    if not clean_path:
        return None

    parsed = parse_storage_reference(clean_path)
    if parsed:
        clean_bucket, clean_path = parsed

    if clean_path.startswith("http://") or clean_path.startswith("https://"):
        return clean_path
    if clean_path.startswith("/files/"):
        return clean_path
    if clean_bucket == "local-phase1" or not clean_bucket:
        return f"/files/{clean_path}"

    base_url = settings.supabase_url.rstrip("/")
    if not base_url:
        return None
    try:
        with httpx.Client(timeout=12) as client:
            response = client.post(
                f"{base_url}/storage/v1/object/sign/{clean_bucket}/{clean_path}",
                headers=_storage_headers(settings, "application/json"),
                json={"expiresIn": settings.signed_url_ttl_seconds},
            )
    except httpx.HTTPError:
        return None
    if response.status_code >= 400:
        return None
    payload: dict[str, Any] = response.json()
    signed_path = payload.get("signedURL") or payload.get("signedUrl") or payload.get("signed_url")
    if not signed_path:
        return None
    signed_text = str(signed_path)
    if signed_text.startswith("http://") or signed_text.startswith("https://"):
        return signed_text
    return f"{base_url}{signed_text if signed_text.startswith('/') else '/' + signed_text}"


def public_or_signed_url(settings: Settings, bucket: str | None, path_or_reference: str | None) -> str | None:
    parsed = parse_storage_reference(path_or_reference)
    if parsed:
        return sign_storage_url(settings, parsed[0], parsed[1])
    return sign_storage_url(settings, bucket, path_or_reference)


async def delete_upload(settings: Settings, bucket: str | None, path_or_reference: str | None) -> None:
    parsed = parse_storage_reference(path_or_reference)
    clean_bucket, clean_path = parsed if parsed else (str(bucket or "").strip(), str(path_or_reference or "").strip())
    clean_path = clean_path.lstrip("/")
    if not clean_path:
        return
    if clean_path.startswith("/files/"):
        clean_path = clean_path.removeprefix("/files/")
    if clean_bucket == "local-phase1" or settings.effective_storage_backend != "supabase":
        target = (settings.upload_dir / clean_path).resolve()
        try:
            if target.is_file() and settings.upload_dir.resolve() in target.parents:
                target.unlink()
        except OSError:
            pass
        return
    base_url = settings.supabase_url.rstrip("/")
    async with httpx.AsyncClient(timeout=12) as client:
        await client.delete(
            f"{base_url}/storage/v1/object/{clean_bucket}/{clean_path}",
            headers=_storage_headers(settings),
        )
