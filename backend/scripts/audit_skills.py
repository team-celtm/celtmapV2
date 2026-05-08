import asyncio
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

async def audit():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    supabase = create_client(url, key)
    
    res = supabase.table("skills").select("id, name").execute()
    print("SKILLS:")
    for s in res.data:
        print(f"- {s['name']} ({s['id']})")
        
    res2 = supabase.table("subskills").select("id, name, skill_id").execute()
    print("\nSUBSKILLS:")
    for ss in res2.data:
        print(f"- {ss['name']} ({ss['id']}) [Skill: {ss['skill_id']}]")

if __name__ == "__main__":
    asyncio.run(audit())
