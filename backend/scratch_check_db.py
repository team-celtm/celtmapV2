
import asyncio
import os
from supabase import create_client
from dotenv import load_dotenv

async def check_db():
    load_dotenv()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") # Use service role for admin access
    if not url or not key:
        print("Missing Supabase credentials")
        return

    supabase = create_client(url, key)
    
    # Check Roles
    roles = supabase.table("roles").select("*").execute()
    print("\n--- ROLES ---")
    for r in roles.data:
        print(f"ID: {r.get('id')} | Name: {r.get('role_name')}")

    # Check Requirements for a few roles
    for r in roles.data[:3]:
        reqs = supabase.table("role_requirements").select("*").eq("role_id", r['id']).execute()
        print(f"\nRequirements for {r.get('role_name')}:")
        for req in reqs.data:
            print(f" - {req.get('skill_name')} (ID: {req.get('skill_id')})")

    # Check Skills
    skills = supabase.table("skills").select("*").limit(5).execute()
    print("\n--- SKILLS (Sample) ---")
    for s in skills.data:
        print(f"ID: {s.get('id')} | Name: {s.get('skill_name')} | Skill_ID: {s.get('skill_id')}")

if __name__ == "__main__":
    asyncio.run(check_db())
