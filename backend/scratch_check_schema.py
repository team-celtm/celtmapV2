
import asyncio
import os
from supabase import create_client
from dotenv import load_dotenv

async def check_schema():
    load_dotenv()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    supabase = create_client(url, key)
    
    # Check one record from role_requirements to see column names
    reqs = supabase.table("role_requirements").select("*").limit(1).execute()
    if reqs.data:
        print("\nRole Requirement Sample:", reqs.data[0])
    else:
        print("\nRole Requirements table is empty.")

if __name__ == "__main__":
    asyncio.run(check_schema())
