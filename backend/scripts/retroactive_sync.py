import asyncio
import os
import sys
from datetime import datetime, UTC

# Add project root to path
sys.path.append(os.getcwd())

from app.config.settings import get_settings
from app.integrations.supabase import get_supabase_client
from app.repositories.assessment_repository import AssessmentRepository
from app.repositories.skill_repository import SkillRepository
from app.repositories.sync_repository import SyncRepository
from app.repositories.report_repository import ReportRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.dashboard_service import DashboardService
from app.services.projection_service import ProjectionService
from app.services.skill_service import SkillService
from app.services.domain_event_service import DomainEventService
from app.utils.text import normalize_name

async def run_sync():
    print("Starting retroactive assessment sync...")
    
    settings = get_settings()
    client = get_supabase_client(settings)
    
    # Initialize components
    assessment_repo = AssessmentRepository(client)
    skill_repo = SkillRepository(client)
    sync_repo = SyncRepository(client)
    profile_repo = ProfileRepository(client)
    report_repo = ReportRepository(client)
    
    event_service = DomainEventService(sync_repo)
    skill_service = SkillService(skill_repo, event_service)
    
    dashboard_service = DashboardService(
        report_repository=report_repo,
        skill_service=skill_service,
        schedule_service=None, # Not needed for projection refresh
        profile_repository=profile_repo
    )
    projection_service = ProjectionService(report_repo, dashboard_service)
    
    # 1. Fetch all completed assessments (those with a score)
    # Supabase execute() is synchronous unless using AsyncClient
    res = client.table("assessments").select("*").not_.is_("overall_score", "null").execute()
    assessments = res.data or []
    
    print(f"Found {len(assessments)} completed assessments to process.")
    
    success_count = 0
    error_count = 0
    synced_users = set()
    
    for assessment in assessments:
        assessment_id = assessment.get("id")
        user_id = assessment.get("user_id")
        score = assessment.get("overall_score") or assessment.get("score") or 0.0
        
        if not user_id or not assessment_id:
            continue
            
        # Inferred category logic: query one question from this assessment
        category = assessment.get("category")
        if not category:
            try:
                # Joining user_answers with questions to get category
                ans_res = client.table("user_answers").select("question_id").eq("assessment_id", assessment_id).limit(1).execute()
                if ans_res.data:
                    q_id = ans_res.data[0].get("question_id")
                    q_res = client.table("questions").select("category").eq("id", q_id).limit(1).execute()
                    if q_res.data:
                        category = q_res.data[0].get("category")
            except Exception as e:
                print(f"  Could not infer category for {assessment_id}: {e}")
        
        if not category:
            print(f"  Skipping assessment {assessment_id}: no category could be determined.")
            continue
            
        skill_id = assessment.get("skill_id") or normalize_name(category)
        
        try:
            print(f"Syncing {category} for user {user_id} (Score: {score})...")
            await skill_service.record_skill_measurement(
                user_id=user_id,
                skill_id=skill_id,
                skill_name=category,
                assessment_score=float(score),
                source="assessment"
            )
            success_count += 1
            synced_users.add(user_id)
        except Exception as e:
            print(f"Error syncing assessment {assessment_id}: {str(e)}")
            error_count += 1
            
    print(f"\nRefreshing dashboard projections for {len(synced_users)} users...")
    for user_id in synced_users:
        try:
            await projection_service.refresh_dashboard_projection(user_id)
            print(f"Refreshed dashboard for user {user_id}")
        except Exception as e:
            print(f"Failed to refresh dashboard for {user_id}: {e}")

    print("\nSync completed!")
    print(f"Processed: {success_count}")
    print(f"Failed: {error_count}")

if __name__ == "__main__":
    asyncio.run(run_sync())
