from __future__ import annotations

import asyncio
import logging
import re
import uuid
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from typing import Any
from xml.etree import ElementTree

from fastapi import UploadFile, HTTPException
from storage3.exceptions import StorageApiError
from supabase import Client

from app.models.enums import DomainEventType
from app.repositories.profile_repository import ProfileRepository
from app.services.domain_event_service import DomainEventService
from app.utils.extraction import extract_text_from_bytes

logger = logging.getLogger(__name__)


class ProfileService:
    def __init__(
        self,
        repository: ProfileRepository,
        client: Client,
        event_service: DomainEventService,
    ) -> None:
        self.repository = repository
        self.client = client
        self.event_service = event_service

    async def _sync_legacy_user_record(self, profile: dict) -> dict:
        user_id = profile.get("id")
        if not user_id:
            return profile

        existing_user = await self.repository.get_user(str(user_id))
        timestamp = datetime.now(timezone.utc).isoformat()
        payload = {
            "id": user_id,
            "email": profile.get("email") or (existing_user or {}).get("email"),
            "full_name": profile.get("full_name") or (existing_user or {}).get("full_name"),
            "avatar_url": profile.get("avatar_url") or (existing_user or {}).get("avatar_url"),
            "role": profile.get("headline") or (existing_user or {}).get("role"),
            "target_role_id": (existing_user or {}).get("target_role_id"),
            "created_at": (existing_user or {}).get("created_at")
            or profile.get("created_at")
            or timestamp,
            "updated_at": timestamp,
        }
        await self.repository.upsert_user(payload)
        return profile

    async def get_profile(self, user_id: str, email: str | None = None, full_name: str | None = None) -> dict:
        profile = await self.repository.get_profile(user_id)
        if profile:
            if not profile.get("full_name") and full_name:
                profile = await self.update_profile(user_id, {"full_name": full_name})
            await self._sync_legacy_user_record(profile)
            return profile
        profile = await self.repository.upsert_profile(
            {
                "id": user_id,
                "email": email,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        await self._sync_legacy_user_record(profile)
        return profile

    def _is_bucket_missing_error(self, exc: StorageApiError) -> bool:
        message = str(exc).lower()
        return "bucket not found" in message or "statuscode': 404" in message

    def _is_bucket_conflict_error(self, exc: StorageApiError) -> bool:
        message = str(exc).lower()
        return (
            "already exists" in message or "duplicate" in message or "statuscode': 409" in message
        )

    async def _ensure_bucket_exists(self, bucket_name: str, public: bool = False) -> None:
        def operation() -> None:
            try:
                self.client.storage.get_bucket(bucket_name)
                return
            except Exception as exc:
                import storage3
                if not isinstance(exc, storage3.exceptions.StorageApiError) or not self._is_bucket_missing_error(exc):
                    # If it's not a missing bucket error, log and maybe raise
                    import logging
                    logging.info(f"Bucket check for {bucket_name} failed: {exc}")
                    if isinstance(exc, storage3.exceptions.StorageApiError):
                        raise

            try:
                self.client.storage.create_bucket(bucket_name, options={"public": public})
            except Exception as exc:
                import storage3
                if not isinstance(exc, storage3.exceptions.StorageApiError) or not self._is_bucket_conflict_error(exc):
                    import logging
                    logging.error(f"Failed to create bucket {bucket_name}: {exc}")
                    if isinstance(exc, storage3.exceptions.StorageApiError):
                        raise

        await asyncio.to_thread(operation)

    async def update_profile(self, user_id: str, payload: dict) -> dict:
        payload = {
            "id": user_id,
            **payload,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        profile = await self.repository.upsert_profile(payload)
        await self._sync_legacy_user_record(profile)
        return profile

    def _extract_text_from_bytes(
        self, *, content: bytes, file_name: str | None, file_type: str
    ) -> str | None:
        text = extract_text_from_bytes(content, file_name=file_name, file_type=file_type)
        return self._normalize_extracted_text(text)

    def _normalize_extracted_text(self, raw_text: str) -> str | None:
        normalized = re.sub(r"\s+", " ", raw_text or "").strip()
        # Keep more context for RAG
        return normalized[:20000] if normalized else None

    def _normalize_artifact_type(self, file_type: str | None, file_name: str | None) -> str:
        requested = str(file_type or "").strip().lower()
        normalized_name = str(file_name or "").strip().lower()

        if requested in {"resume", "cv"}:
            return "resume"
        if requested in {"credential", "credentials", "certificate", "certification", "license"}:
            return "certificate"
        if requested == "written_assessment":
            return "written_assessment"

        if any(token in normalized_name for token in ("resume", "curriculum-vitae", "curriculum_vitae", "cv")):
            return "resume"
        if any(token in normalized_name for token in ("certificate", "certification", "credential", "license")):
            return "certificate"

        return "document"

    async def _sync_profile_assets_metadata(
        self,
        *,
        user_id: str,
        file_name: str,
        file_type: str,
    ) -> None:
        profile = await self.repository.get_profile(user_id)
        metadata = dict((profile or {}).get("metadata") or {})
        profile_assets = dict(metadata.get("profile_assets") or {})

        supporting_names = [
            str(item).strip()
            for item in profile_assets.get("supportingCertificateNames") or []
            if str(item).strip()
        ]

        if file_type == "resume":
            profile_assets["resumeName"] = file_name
        elif file_type == "certificate":
            primary_name = str(profile_assets.get("primaryCertificateName") or "").strip()
            if not primary_name or primary_name == file_name:
                profile_assets["primaryCertificateName"] = file_name
            elif file_name not in supporting_names:
                supporting_names.append(file_name)
            profile_assets["supportingCertificateNames"] = supporting_names

        metadata["profile_assets"] = {
            "resumeName": str(profile_assets.get("resumeName") or ""),
            "primaryCertificateName": str(profile_assets.get("primaryCertificateName") or ""),
            "supportingCertificateNames": supporting_names,
        }

        await self.update_profile(user_id, {"metadata": metadata})

    async def list_artifacts(self, user_id: str) -> list[dict]:
        return await self.repository.list_artifacts(user_id, limit=200)

    async def upload_avatar(self, user_id: str, upload: UploadFile, bucket_name: str) -> dict:
        content = await upload.read()
        file_ext = upload.filename.split(".")[-1] if upload.filename else "bin"
        storage_path = f"{user_id}/avatar-{uuid.uuid4()}.{file_ext}"
        await self._ensure_bucket_exists(bucket_name)

        def operation() -> Any:
            return self.client.storage.from_(bucket_name).upload(
                storage_path,
                content,
                {"content-type": upload.content_type or "application/octet-stream"},
            )

        await asyncio.to_thread(operation)
        avatar_url = f"{bucket_name}/{storage_path}"
        return await self.update_profile(user_id, {"avatar_url": avatar_url})


    async def upload_artifact(
        self,
        user_id: str,
        upload: UploadFile,
        bucket_name: str = "artifacts",
        file_type: str = "resume",
    ) -> dict:
        logger.info("Starting artifact upload for user %s, file %s", user_id, upload.filename)

        content = await upload.read()
        if not content:
            logger.warning("Empty file content received")
            return {"error": "Empty file", "status": "failed"}

        normalized_file_type = self._normalize_artifact_type(file_type, upload.filename)

        # Extract text first to ensure we have something to parse
        try:
            extracted_text = self._extract_text_from_bytes(
                content=content,
                file_name=upload.filename,
                file_type=upload.content_type or normalized_file_type,
            )
        except Exception as exc:
            logger.warning("Sync text extraction failed for %s: %s", upload.filename, exc)
            extracted_text = None

        try:
            await self._ensure_bucket_exists(bucket_name)
        except StorageApiError:
            raise HTTPException(status_code=503, detail="Storage service temporarily unavailable. Please try again.")

        safe_filename = "".join(
            [c if c.isalnum() or c in "._-" else "_" for c in (upload.filename or "artifact")]
        )
        storage_path = f"{user_id}/{datetime.now(timezone.utc).timestamp()}_{safe_filename}"

        try:
            # Upload to Supabase Storage
            await asyncio.to_thread(
                self.client.storage.from_(bucket_name).upload,
                path=storage_path,
                file=content,
                file_options={"content-type": upload.content_type or "application/octet-stream"},
            )
            logger.info("Successfully uploaded %s to storage", storage_path)
        except Exception as exc:
            logger.error("Storage upload failed — aborting artifact creation for %s: %s", upload.filename, exc)
            raise

        # Construct the Public URL for the artifact
        try:
            # First try the standard SDK way
            file_url_obj = self.client.storage.from_(bucket_name).get_public_url(storage_path)
            file_url = str(file_url_obj) if file_url_obj else ""
            if not file_url and hasattr(file_url_obj, 'public_url'): # Handle different SDK versions
                file_url = file_url_obj.public_url
        except Exception:
            # Fallback construction
            base_url = str(self.client.supabase_url).rstrip("/")
            file_url = f"{base_url}/storage/v1/object/public/{bucket_name}/{storage_path}"

        # Create record in database
        # This payload matches the unified schema in sql/repair_schema.sql
        artifact_record = {
            "user_id": user_id,
            "bucket_name": bucket_name,
            "storage_path": storage_path,
            "file_name": upload.filename or safe_filename,
            "file_type": normalized_file_type,
            "file_url": file_url,
            "extracted_text": extracted_text,
            "metadata": {
                "content_type": upload.content_type,
                "size": len(content),
                "processing_status": "queued",
                "upload_source": file_type,
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            inserted = await self.repository.insert_artifact(artifact_record)
            
            if not inserted or not inserted.get("id"):
                logger.error("Database persistence failed - no ID returned. Record: %s", artifact_record)
                return {"error": "Persistence failed", "status": "failed"}

            logger.info("Successfully persisted artifact record: %s", inserted.get("id"))

            await self._sync_profile_assets_metadata(
                user_id=user_id,
                file_name=artifact_record["file_name"],
                file_type=normalized_file_type,
            )

            # --- CONNECT TO ENHANCED RAG ---
            if extracted_text:
                try:
                    from enhanced_rag_integration import get_pipeline_instance
                    pipeline = get_pipeline_instance()
                    if pipeline:
                        logger.info("RAG INDEX START - Artifact ID: %s", inserted.get("id"))
                        logger.info("DOCUMENT LENGTH: %d characters", len(extracted_text))
                        
                        await pipeline.index_document(
                            document_id=str(inserted.get("id")),
                            text=extracted_text,
                            metadata={
                                "user_id": user_id,
                                "filename": upload.filename or safe_filename,
                                "artifact_type": normalized_file_type,
                                "source": "upload"
                            }
                        )
                        logger.info("RAG INDEX SUCCESS - Artifact ID: %s", inserted.get("id"))
                    else:
                        logger.warning("RAG INDEX SKIP - Pipeline instance not initialized")
                except Exception as rag_exc:
                    logger.error("RAG INDEX ERROR - Failed to index artifact %s: %s", inserted.get("id"), rag_exc)
            # -------------------------------

            try:
                from app.tasks.artifacts import extract_uploaded_artifact
                extract_uploaded_artifact.delay(str(inserted.get("id")))
            except Exception as task_exc:
                logger.error("Background task initiation failed for artifact: %s", task_exc)
                metadata_update = dict((inserted or {}).get("metadata") or {})
                metadata_update["processing_status"] = "failed"
                metadata_update["processing_error"] = "Background task could not be dispatched"
                await self.repository.update_artifact(str(inserted.get("id")), {"metadata": metadata_update})

            # Emit event for background processing (trajectories, skill detection, etc)
            await self.event_service.emit(
                event_type=DomainEventType.ARTIFACT_UPLOADED,
                aggregate_type="artifact",
                aggregate_id=str(inserted.get("id")),
                payload={
                    "user_id": user_id,
                    "artifact_id": str(inserted.get("id")),
                    "file_type": normalized_file_type,
                },
            )
            return await self.repository.get_artifact(str(inserted.get("id"))) or inserted
        except Exception as exc:
            logger.error(
                "Final database persistence failure for artifact: %s. Payload: %s", 
                exc, 
                artifact_record
            )
            # Fallback: maybe the schema isn't unified yet? 
            # We try a minimal insert if the full one fails, but it's better to fail and inform.
            raise

    async def delete_artifact(self, user_id: str, artifact_id: str) -> bool:
        artifact = await self.repository.get_artifact(artifact_id)
        if not artifact or str(artifact.get("user_id")) != user_id:
            raise HTTPException(status_code=404, detail="Artifact not found or access denied")
        
        try:
            # Delete from storage if possible
            bucket_name = artifact.get("bucket_name") or "career-artifacts"
            storage_path = artifact.get("storage_path")
            if storage_path:
                await asyncio.to_thread(
                    self.client.storage.from_(bucket_name).remove,
                    [storage_path]
                )
        except Exception as exc:
            logger.warning("Failed to remove artifact %s from storage: %s", artifact_id, exc)

        # Delete from database
        await self.repository.delete_artifact(artifact_id)
        return True

    async def replace_artifact(
        self,
        user_id: str,
        artifact_id: str,
        upload: UploadFile,
    ) -> dict:
        artifact = await self.repository.get_artifact(artifact_id)
        if not artifact or str(artifact.get("user_id")) != user_id:
            raise HTTPException(status_code=404, detail="Artifact not found or access denied")
        
        bucket_name = artifact.get("bucket_name") or "career-artifacts"
        old_storage_path = artifact.get("storage_path")
        file_type = artifact.get("file_type") or "certificate"

        content = await upload.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty file")

        normalized_file_type = self._normalize_artifact_type(file_type, upload.filename)

        try:
            extracted_text = self._extract_text_from_bytes(
                content=content,
                file_name=upload.filename,
                file_type=upload.content_type or normalized_file_type,
            )
        except Exception as exc:
            logger.warning("Sync text extraction failed for %s: %s", upload.filename, exc)
            extracted_text = None

        safe_filename = "".join(
            [c if c.isalnum() or c in "._-" else "_" for c in (upload.filename or "artifact")]
        )
        new_storage_path = f"{user_id}/{datetime.now(timezone.utc).timestamp()}_{safe_filename}"

        await asyncio.to_thread(
            self.client.storage.from_(bucket_name).upload,
            path=new_storage_path,
            file=content,
            file_options={"content-type": upload.content_type or "application/octet-stream"},
        )

        if old_storage_path:
            try:
                await asyncio.to_thread(
                    self.client.storage.from_(bucket_name).remove,
                    [old_storage_path]
                )
            except Exception as exc:
                logger.warning("Failed to remove old artifact %s from storage: %s", old_storage_path, exc)

        try:
            file_url_obj = self.client.storage.from_(bucket_name).get_public_url(new_storage_path)
            file_url = str(file_url_obj) if file_url_obj else ""
            if not file_url and hasattr(file_url_obj, 'public_url'):
                file_url = file_url_obj.public_url
        except Exception:
            base_url = str(self.client.supabase_url).rstrip("/")
            file_url = f"{base_url}/storage/v1/object/public/{bucket_name}/{new_storage_path}"

        update_payload = {
            "storage_path": new_storage_path,
            "file_name": upload.filename or safe_filename,
            "file_type": normalized_file_type,
            "file_url": file_url,
            "extracted_text": extracted_text,
            "metadata": {
                **(artifact.get("metadata") or {}),
                "content_type": upload.content_type,
                "size": len(content),
                "processing_status": "queued",
            },
        }

        updated = await self.repository.update_artifact(artifact_id, update_payload)

        try:
            from app.tasks.artifacts import extract_uploaded_artifact
            extract_uploaded_artifact.delay(artifact_id)
        except Exception as task_exc:
            logger.error("Background task initiation failed for artifact update: %s", task_exc)
            
        return updated or update_payload
