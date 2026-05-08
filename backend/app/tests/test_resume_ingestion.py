import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import UploadFile, HTTPException
from storage3.exceptions import StorageApiError

from app.services.profile_service import ProfileService
from app.tasks.artifacts import _extract_artifact


class FakeProfileRepository:
    def __init__(self):
        self.artifacts = {}
        self.insert_call_count = 0
        self.update_call_count = 0
        self.profile = {"metadata": {}}

    async def get_profile(self, user_id: str):
        return {"id": user_id, "metadata": {}}

    async def update_profile(self, user_id: str, payload: dict):
        self.profile.update(payload)
        return self.profile

    async def upsert_profile(self, payload: dict):
        self.profile.update(payload)
        return self.profile

    async def get_user(self, user_id: str):
        return {"id": user_id}

    async def upsert_user(self, payload: dict):
        return payload

    async def insert_artifact(self, payload: dict):
        self.insert_call_count += 1
        artifact_id = f"art-{self.insert_call_count}"
        payload["id"] = artifact_id
        self.artifacts[artifact_id] = payload
        return payload

    async def get_artifact(self, artifact_id: str):
        return self.artifacts.get(artifact_id)

    async def update_artifact(self, artifact_id: str, payload: dict):
        self.update_call_count += 1
        if artifact_id in self.artifacts:
            self.artifacts[artifact_id].update(payload)
            if "metadata" in payload:
                # Merge metadata
                old_meta = self.artifacts[artifact_id].get("metadata", {})
                old_meta.update(payload["metadata"])
                self.artifacts[artifact_id]["metadata"] = old_meta


class FakeEventService:
    async def emit(self, **kwargs):
        pass


class FakeSkillRepository:
    def __init__(self):
        self.upsert_call_count = 0

    async def upsert_hidden_candidate(self, payload):
        self.upsert_call_count += 1


class FakeSettings:
    artifact_bucket = "artifacts"
    openai_api_key = "test"
    supabase_url = "test"
    supabase_service_role_key = "test"


@pytest.fixture
def fake_client():
    client = MagicMock()
    # Mock storage
    client.storage.get_bucket = MagicMock()
    client.storage.create_bucket = MagicMock()

    upload_mock = MagicMock()
    url_mock = MagicMock()
    url_mock.return_value = "http://test.com/file"

    from_mock = MagicMock()
    from_mock.upload = upload_mock
    from_mock.get_public_url = url_mock
    from_mock.download = MagicMock(return_value=b"some bytes")

    client.storage.from_ = MagicMock(return_value=from_mock)
    client.supabase_url = "http://test.com"
    return client


@pytest.fixture
def fake_upload_file():
    file = MagicMock(spec=UploadFile)
    file.filename = "test.pdf"
    file.content_type = "application/pdf"
    file.read = AsyncMock(return_value=b"fake pdf content")
    return file


@pytest.mark.asyncio
async def test_happy_path(fake_client, fake_upload_file):
    repo = FakeProfileRepository()
    service = ProfileService(repo, client=fake_client, event_service=FakeEventService())

    # Mock extract_text
    service._extract_text_from_bytes = MagicMock(return_value="Extracted text here")

    with patch("app.tasks.artifacts.extract_uploaded_artifact.delay") as mock_delay:
        result = await service.upload_artifact("user-1", fake_upload_file)

        assert "error" not in result
        assert repo.insert_call_count == 1
        assert mock_delay.call_count == 1

        # Now simulate background task
        skill_repo = FakeSkillRepository()

        with patch("app.tasks.artifacts.extract_text_from_bytes") as mock_fallback:
            with patch("app.services.rag_service.RagService.upsert_documents", new_callable=AsyncMock) as mock_upsert:
                with patch("app.tasks.trajectory.bootstrap_user_trajectory.delay"):
                    with patch("app.tasks.projections.refresh_dashboard_projection.delay"):
                        with patch("app.tasks.reports.generate_user_report.delay"):
                            res = await _extract_artifact(
                                artifact_id=result["id"],
                                profile_repository=repo,
                                skill_repository=skill_repo,
                                skill_service=MagicMock(),
                                client=fake_client,
                                settings=FakeSettings()
                            )

                            assert res["status"] == "completed"
                            artifact = await repo.get_artifact(result["id"])
                            assert artifact["metadata"]["processing_status"] == "completed"


@pytest.mark.asyncio
async def test_sync_extraction_failure(fake_client, fake_upload_file):
    repo = FakeProfileRepository()
    service = ProfileService(repo, client=fake_client, event_service=FakeEventService())

    # Mock extract_text to raise error
    service._extract_text_from_bytes = MagicMock(side_effect=Exception("PDFReadError"))

    with patch("app.tasks.artifacts.extract_uploaded_artifact.delay") as mock_delay:
        result = await service.upload_artifact("user-1", fake_upload_file)

        # Pipeline must continue
        assert repo.insert_call_count == 1
        assert mock_delay.call_count == 1
        artifact = await repo.get_artifact(result["id"])
        assert artifact["extracted_text"] is None


@pytest.mark.asyncio
async def test_storage_upload_failure(fake_client, fake_upload_file):
    repo = FakeProfileRepository()
    service = ProfileService(repo, client=fake_client, event_service=FakeEventService())
    service._extract_text_from_bytes = MagicMock(return_value="Text")

    # Mock upload to fail
    fake_client.storage.from_().upload.side_effect = Exception("Storage fail")

    with pytest.raises(Exception, match="Storage fail"):
        await service.upload_artifact("user-1", fake_upload_file)

    assert repo.insert_call_count == 0


@pytest.mark.asyncio
async def test_celery_dispatch_failure(fake_client, fake_upload_file):
    repo = FakeProfileRepository()
    service = ProfileService(repo, client=fake_client, event_service=FakeEventService())
    service._extract_text_from_bytes = MagicMock(return_value="Text")

    # Mock delay to fail
    with patch("app.tasks.artifacts.extract_uploaded_artifact.delay", side_effect=Exception("Redis down")):
        result = await service.upload_artifact("user-1", fake_upload_file)

        assert repo.insert_call_count == 1
        artifact = await repo.get_artifact(result["id"])
        assert artifact["metadata"]["processing_status"] == "failed"
        assert artifact["metadata"]["processing_error"] == "Background task could not be dispatched"


@pytest.mark.asyncio
async def test_fallback_extraction_failure(fake_client):
    repo = FakeProfileRepository()
    # Create artifact with no text
    art = await repo.insert_artifact({
        "user_id": "user-1",
        "file_name": "test.pdf",
        "file_type": "resume",
        "extracted_text": None,
        "metadata": {}
    })

    skill_repo = FakeSkillRepository()

    # Mock fallback download to fail
    fake_client.storage.from_().download.side_effect = Exception("Download failed")

    with patch("app.services.rag_service.RagService.upsert_documents", new_callable=AsyncMock) as mock_upsert:
        res = await _extract_artifact(
            artifact_id=art["id"],
            profile_repository=repo,
            skill_repository=skill_repo,
            skill_service=MagicMock(),
            client=fake_client,
            settings=FakeSettings()
        )

        assert res["status"] == "failed"
        artifact = await repo.get_artifact(art["id"])
        assert artifact["metadata"]["processing_status"] == "failed"
        assert artifact["metadata"]["processing_error"] == "Text extraction failed after fallback attempt"
        assert skill_repo.upsert_call_count == 0
        assert mock_upsert.call_count == 0


@pytest.mark.asyncio
async def test_bucket_unavailable(fake_client, fake_upload_file):
    repo = FakeProfileRepository()
    service = ProfileService(repo, client=fake_client, event_service=FakeEventService())
    service._extract_text_from_bytes = MagicMock(return_value="Text")

    # Mock bucket exists check to raise StorageApiError
    fake_client.storage.get_bucket.side_effect = StorageApiError("Timeout", "503", "503")
    fake_client.storage.create_bucket.side_effect = StorageApiError("Timeout", "503", "503")

    with pytest.raises(HTTPException) as excinfo:
        await service.upload_artifact("user-1", fake_upload_file)

    assert excinfo.value.status_code == 503
    assert "Storage service temporarily unavailable" in str(excinfo.value.detail)
    assert repo.insert_call_count == 0
