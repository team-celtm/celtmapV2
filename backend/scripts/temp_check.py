import asyncio
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

async def main():
    from app.config.settings import get_settings
    from app.integrations.supabase import get_supabase_client
    
    settings = get_settings()
    client = get_supabase_client(settings)
    
    tables = ["questions", "question_options", "mcq_questions", "situational_mcq_questions"]
    for table in tables:
        try:
            res = client.table(table).select("id", count="exact").limit(1).execute()
            print(f"{table}: {res.count}")
        except Exception as e:
            msg = str(e)
            if "not find" in msg:
                print(f"{table}: MISSING")
            else:
                print(f"{table}: error - {msg}")

if __name__ == "__main__":
    asyncio.run(main())
