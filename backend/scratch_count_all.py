
import asyncio
import os
from supabase import create_client
from dotenv import load_dotenv

async def check_content():
    load_dotenv()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    supabase = create_client(url, key)
    
    tables = ["questions", "mcq_questions", "assessment_banks", "roles", "role_requirements"]
    
    for table in tables:
        try:
            res = supabase.table(table).select("count", count="exact").limit(0).execute()
            print(f"Table '{table}' count: {res.count}")
        except Exception as e:
            print(f"Table '{table}' could not be counted: {e}")

if __name__ == "__main__":
    asyncio.run(check_content())
