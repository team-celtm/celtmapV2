from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from supabase import Client

from app.config.settings import Settings, get_settings
from app.core.exceptions import AppError
from app.integrations.cache import CacheClient
from app.integrations.llm import OpenAIProvider
from app.integrations.neo4j_client import get_neo4j_driver
from app.integrations.supabase import get_supabase_client
from app.integrations.transcription import PlaceholderTranscriptionProvider
from app.repositories.assessment_repository import AssessmentRepository
from app.repositories.interview_repository import InterviewRepository
from app.repositories.learning_repository import LearningRepository
from app.repositories.ops_repository import OpsRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.rag_repository import RagRepository
from app.repositories.report_repository import ReportRepository
from app.repositories.schedule_repository import ScheduleRepository
from app.repositories.skill_repository import SkillRepository
from app.repositories.sync_repository import SyncRepository
from app.services.admin_auth_service import AdminAuthService
from app.services.admin_auth_service import AdminAuthService
from app.services.admin_csv_service import AdminCSVService
from app.services.admin_service import AdminService
from app.services.auth_service import AuthService
from app.services.celtmind_sync import CeltmindSyncService
from app.services.dashboard_service import DashboardService
from app.services.domain_event_service import DomainEventService
from app.services.evaluation_service import EvaluationService
from app.services.graph_sync_service import GraphSyncService
from app.services.interview_service import InterviewService
from app.services.learning_service import LearningService
from app.services.mcq_service import MCQService
from app.services.ops_service import OpsService
from app.services.profile_service import ProfileService
from app.services.projection_service import ProjectionService
from app.services.rag_service import RagService
from app.services.report_service import ReportService
from app.services.schedule_service import ScheduleService
from app.services.settings_service import SettingsService
from app.services.skill_request_service import SkillRequestService
from app.services.skill_service import SkillService
from app.services.trajectory_service import TrajectoryService
from app.services.written_assessment_service import WrittenAssessmentService


def get_app_settings() -> Settings:
    return get_settings()


def get_supabase() -> Client:
    settings = get_settings()
    try:
        settings.require_supabase()
        return get_supabase_client(settings)
    except ValueError as exc:
        raise AppError(
            message=str(exc),
            status_code=503,
            error_code="supabase_not_configured",
        ) from exc


def get_cache() -> CacheClient:
    return CacheClient(get_settings())


def get_openai_provider(
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> OpenAIProvider:
    return OpenAIProvider(settings)


def get_auth_service(
    client: Annotated[Client, Depends(get_supabase)],
) -> AuthService:
    return AuthService(client)


def get_profile_repository(
    client: Annotated[Client, Depends(get_supabase)],
) -> ProfileRepository:
    return ProfileRepository(client)


def get_assessment_repository(
    client: Annotated[Client, Depends(get_supabase)],
) -> AssessmentRepository:
    return AssessmentRepository(client)


def get_skill_repository(
    client: Annotated[Client, Depends(get_supabase)],
) -> SkillRepository:
    return SkillRepository(client)


def get_interview_repository(
    client: Annotated[Client, Depends(get_supabase)],
) -> InterviewRepository:
    return InterviewRepository(client)


def get_learning_repository(
    client: Annotated[Client, Depends(get_supabase)],
) -> LearningRepository:
    return LearningRepository(client)


def get_schedule_repository(
    client: Annotated[Client, Depends(get_supabase)],
) -> ScheduleRepository:
    return ScheduleRepository(client)


def get_report_repository(
    client: Annotated[Client, Depends(get_supabase)],
) -> ReportRepository:
    return ReportRepository(client)


def get_sync_repository(
    client: Annotated[Client, Depends(get_supabase)],
) -> SyncRepository:
    return SyncRepository(client)


def get_rag_repository(
    client: Annotated[Client, Depends(get_supabase)],
) -> RagRepository:
    return RagRepository(client)


def get_ops_repository(
    client: Annotated[Client, Depends(get_supabase)],
) -> OpsRepository:
    return OpsRepository(client)


def get_domain_event_service(
    repository: Annotated[SyncRepository, Depends(get_sync_repository)],
) -> DomainEventService:
    return DomainEventService(repository)


def get_ops_service(
    repository: Annotated[OpsRepository, Depends(get_ops_repository)],
) -> OpsService:
    return OpsService(repository)


def get_profile_service(
    repository: Annotated[ProfileRepository, Depends(get_profile_repository)],
    client: Annotated[Client, Depends(get_supabase)],
    event_service: Annotated[DomainEventService, Depends(get_domain_event_service)],
) -> ProfileService:
    return ProfileService(repository, client, event_service)


def get_settings_service(
    repository: Annotated[ProfileRepository, Depends(get_profile_repository)],
) -> SettingsService:
    return SettingsService(repository)


def get_skill_service(
    repository: Annotated[SkillRepository, Depends(get_skill_repository)],
    event_service: Annotated[DomainEventService, Depends(get_domain_event_service)],
    assessment_repository: Annotated[AssessmentRepository, Depends(get_assessment_repository)],
) -> SkillService:
    return SkillService(repository, event_service, assessment_repository)


def get_rag_service(
    settings: Annotated[Settings, Depends(get_app_settings)],
    cache: Annotated[CacheClient, Depends(get_cache)],
    repository: Annotated[RagRepository, Depends(get_rag_repository)],
    report_repository: Annotated[ReportRepository, Depends(get_report_repository)],
    profile_repository: Annotated[ProfileRepository, Depends(get_profile_repository)],
    llm_provider: Annotated[OpenAIProvider, Depends(get_openai_provider)],
    ops_service: Annotated[OpsService, Depends(get_ops_service)],
) -> RagService:
    return RagService(
        settings=settings,
        cache=cache,
        repository=repository,
        report_repository=report_repository,
        profile_repository=profile_repository,
        llm_provider=llm_provider,
        ops_service=ops_service,
    )


def get_evaluation_service(
    llm_provider: Annotated[OpenAIProvider, Depends(get_openai_provider)],
) -> EvaluationService:
    return EvaluationService(llm_provider)


def get_transcription_provider() -> PlaceholderTranscriptionProvider:
    return PlaceholderTranscriptionProvider(get_settings())


def get_graph_sync_service(
    repository: Annotated[SkillRepository, Depends(get_skill_repository)],
) -> GraphSyncService:
    return GraphSyncService(repository, get_neo4j_driver(get_settings()))


def get_mcq_service(
    repository: Annotated[AssessmentRepository, Depends(get_assessment_repository)],
    event_service: Annotated[DomainEventService, Depends(get_domain_event_service)],
    skill_service: Annotated[SkillService, Depends(get_skill_service)],
    skill_request_service: Annotated[SkillRequestService, Depends(get_skill_request_service)],
    interview_repository: Annotated[InterviewRepository, Depends(get_interview_repository)],
    learning_repository: Annotated[LearningRepository, Depends(get_learning_repository)],
    profile_repository: Annotated[ProfileRepository, Depends(get_profile_repository)],
    rag_service: Annotated[RagService, Depends(get_rag_service)],
    projection_service: Annotated[ProjectionService, Depends(get_projection_service)],
    cache: Annotated[CacheClient, Depends(get_cache)],
) -> MCQService:
    return MCQService(
        repository,
        event_service,
        skill_service,
        skill_request_service,
        interview_repository,
        learning_repository,
        profile_repository,
        rag_service,
        projection_service,
        cache=cache,
    )


def get_interview_service(
    repository: Annotated[InterviewRepository, Depends(get_interview_repository)],
    event_service: Annotated[DomainEventService, Depends(get_domain_event_service)],
) -> InterviewService:
    return InterviewService(repository, event_service)


def get_skill_request_service(
    repository: Annotated[SkillRepository, Depends(get_skill_repository)],
    assessment_repository: Annotated[AssessmentRepository, Depends(get_assessment_repository)],
    rag_service: Annotated[RagService, Depends(get_rag_service)],
    llm_provider: Annotated[OpenAIProvider, Depends(get_openai_provider)],
    ops_service: Annotated[OpsService, Depends(get_ops_service)],
    schedule_service: Annotated[ScheduleService, Depends(get_schedule_service)],
    event_service: Annotated[DomainEventService, Depends(get_domain_event_service)],
) -> SkillRequestService:
    return SkillRequestService(
        repository=repository,
        assessment_repository=assessment_repository,
        rag_service=rag_service,
        llm_provider=llm_provider,
        ops_service=ops_service,
        schedule_service=schedule_service,
        event_service=event_service,
    )


def get_written_assessment_service(
    repository: Annotated[AssessmentRepository, Depends(get_assessment_repository)],
    skill_repository: Annotated[SkillRepository, Depends(get_skill_repository)],
) -> WrittenAssessmentService:
    return WrittenAssessmentService(repository, skill_repository)


def get_learning_service(
    repository: Annotated[LearningRepository, Depends(get_learning_repository)],
    profile_repository: Annotated[ProfileRepository, Depends(get_profile_repository)],
    skill_service: Annotated[SkillService, Depends(get_skill_service)],
    rag_service: Annotated[RagService, Depends(get_rag_service)],
    mcq_service: Annotated[MCQService, Depends(get_mcq_service)],
    cache: Annotated[CacheClient, Depends(get_cache)],
) -> LearningService:
    return LearningService(
        repository,
        profile_repository,
        skill_service,
        rag_service,
        mcq_service,
        cache=cache,
    )


def get_trajectory_service(
    repository: Annotated[LearningRepository, Depends(get_learning_repository)],
    profile_repository: Annotated[ProfileRepository, Depends(get_profile_repository)],
    skill_repository: Annotated[SkillRepository, Depends(get_skill_repository)],
    skill_service: Annotated[SkillService, Depends(get_skill_service)],
    learning_service: Annotated[LearningService, Depends(get_learning_service)],
    skill_request_service: Annotated[SkillRequestService, Depends(get_skill_request_service)],
    event_service: Annotated[DomainEventService, Depends(get_domain_event_service)],
) -> TrajectoryService:
    return TrajectoryService(
        repository,
        profile_repository,
        skill_repository,
        skill_service,
        learning_service,
        skill_request_service,
        event_service,
    )


def get_schedule_service(
    repository: Annotated[ScheduleRepository, Depends(get_schedule_repository)],
) -> ScheduleService:
    return ScheduleService(repository)


def get_report_service(
    report_repository: Annotated[ReportRepository, Depends(get_report_repository)],
    assessment_repository: Annotated[AssessmentRepository, Depends(get_assessment_repository)],
    interview_repository: Annotated[InterviewRepository, Depends(get_interview_repository)],
    skill_service: Annotated[SkillService, Depends(get_skill_service)],
    profile_repository: Annotated[ProfileRepository, Depends(get_profile_repository)],
) -> ReportService:
    return ReportService(
        report_repository,
        assessment_repository,
        interview_repository,
        skill_service,
        profile_repository,
    )


def get_dashboard_service(
    report_repository: Annotated[ReportRepository, Depends(get_report_repository)],
    skill_service: Annotated[SkillService, Depends(get_skill_service)],
    schedule_service: Annotated[ScheduleService, Depends(get_schedule_service)],
    profile_repository: Annotated[ProfileRepository, Depends(get_profile_repository)],
) -> DashboardService:
    return DashboardService(report_repository, skill_service, schedule_service, profile_repository)


def get_projection_service(
    repository: Annotated[ReportRepository, Depends(get_report_repository)],
    dashboard_service: Annotated[DashboardService, Depends(get_dashboard_service)],
) -> ProjectionService:
    return ProjectionService(repository, dashboard_service)


def get_celtmind_sync_service(
    sync_repository: Annotated[SyncRepository, Depends(get_sync_repository)],
    assessment_repository: Annotated[AssessmentRepository, Depends(get_assessment_repository)],
    skill_repository: Annotated[SkillRepository, Depends(get_skill_repository)],
    rag_service: Annotated[RagService, Depends(get_rag_service)],
    event_service: Annotated[DomainEventService, Depends(get_domain_event_service)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> CeltmindSyncService:
    return CeltmindSyncService(
        sync_repository=sync_repository,
        assessment_repository=assessment_repository,
        skill_repository=skill_repository,
        rag_service=rag_service,
        event_service=event_service,
        celtmind_path=settings.celtmind_path,
    )


def get_admin_auth_service(
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> AdminAuthService:
    return AdminAuthService(settings)


def get_admin_csv_service(
    assessment_repo: Annotated[AssessmentRepository, Depends(get_assessment_repository)],
    skill_repo: Annotated[SkillRepository, Depends(get_skill_repository)],
    profile_repo: Annotated[ProfileRepository, Depends(get_profile_repository)],
) -> AdminCSVService:
    return AdminCSVService(assessment_repo, skill_repo, profile_repo)


def get_admin_service(
    sync_service: Annotated[CeltmindSyncService, Depends(get_celtmind_sync_service)],
    sync_repository: Annotated[SyncRepository, Depends(get_sync_repository)],
) -> AdminService:
    return AdminService(sync_service, sync_repository)
