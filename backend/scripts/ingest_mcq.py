from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


async def main() -> None:
    from app.config.settings import get_settings
    from app.integrations.cache import CacheClient
    from app.integrations.llm import OpenAIProvider
    from app.integrations.supabase import get_supabase_client
    from app.repositories.assessment_repository import AssessmentRepository
    from app.repositories.ops_repository import OpsRepository
    from app.repositories.rag_repository import RagRepository
    from app.repositories.report_repository import ReportRepository
    from app.repositories.skill_repository import SkillRepository
    from app.repositories.sync_repository import SyncRepository
    from app.services.celtmind_sync import CeltmindSyncService
    from app.services.domain_event_service import DomainEventService
    from app.services.ops_service import OpsService
    from app.services.rag_service import RagService

    settings = get_settings()
    client = get_supabase_client(settings)
    sync_repository = SyncRepository(client)
    assessment_repository = AssessmentRepository(client)
    event_service = DomainEventService(sync_repository)
    rag_service = RagService(
        settings=settings,
        cache=CacheClient(settings),
        repository=RagRepository(client),
        report_repository=ReportRepository(client),
        llm_provider=OpenAIProvider(settings),
        ops_service=OpsService(OpsRepository(client)),
    )
    service = CeltmindSyncService(
        sync_repository=sync_repository,
        assessment_repository=assessment_repository,
        skill_repository=SkillRepository(client),
        rag_service=rag_service,
        event_service=event_service,
        celtmind_path=settings.celtmind_path,
    )
    result = await service.sync()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
