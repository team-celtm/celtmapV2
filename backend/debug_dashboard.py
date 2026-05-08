import asyncio
import os
import sys

# Ensure backend directory is in path
sys.path.append(os.getcwd())

from app.db.supabase import supabase
from app.services.skill_service import SkillService
from app.services.dashboard_service import DashboardService
from app.repositories.skill_repository import SkillRepository
from app.repositories.assessment_repository import AssessmentRepository

async def debug_user(email: str):
    print(f"--- Debugging {email} ---")
    res = supabase.table("profiles").select("id, full_name").eq("email", email).execute()
    if not res.data:
        print("User not found")
        return
    
    user = res.data[0]
    user_id = user["id"]
    print(f"User ID: {user_id}")
    print(f"Name: {user.get('full_name')}")
    
    # Check assessments
    mcqs = supabase.table("assessments").select("*").eq("user_id", user_id).execute()
    print(f"MCQ Assessments: {len(mcqs.data)}")
    for m in mcqs.data:
        print(f"  - Assessment {m.get('id')} | Skill: {m.get('skill_id')} | Category: {m.get('category')} | Score: {m.get('overall_score')}")
        
    written = supabase.table("written_assessments").select("*").eq("user_id", user_id).execute()
    print(f"Written Assessments: {len(written.data)}")
    
    # Check user_skills
    skills = supabase.table("user_skills").select("*").eq("user_id", user_id).execute()
    print(f"User Skills Records: {len(skills.data)}")
    
    # Try recovery
    skill_repo = SkillRepository(supabase)
    assess_repo = AssessmentRepository(supabase)
    skill_service = SkillService(skill_repo, assess_repo)
    
    print("\n--- Running Recovery Logically ---")
    recovered = await skill_service.recalculate_from_assessments(user_id)
    print(f"Recovery count: {len(recovered)}")
    
    domain_readiness = await skill_service.get_domain_readiness(user_id)
    print(f"Domain Readiness: {domain_readiness}")

if __name__ == "__main__":
    asyncio.run(debug_user("zian.surani@gmail.com"))
