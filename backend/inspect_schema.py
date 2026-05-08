import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not URL or not KEY:
    print("Missing environment variables")
    exit(1)

supabase = create_client(URL, KEY)

TABLES = [
    "learning_paths",
    "learning_modules",
    "trajectory_roles",
    "reports",
    "dashboard_projections",
    "profiles",
    "user_preferences",
    "uploaded_artifacts",
    "schedule_events",
    "questions",
    "question_options"
]

for table in TABLES:
    print(f"\n--- Table: {table} ---")
    try:
        # Get one row to see columns
        res = supabase.table(table).select("*").limit(1).execute()
        if res.data:
            print(f"Columns: {list(res.data[0].keys())}")
        else:
            print("No data in table to inspect columns. Checking schema via RPC if possible or generic select.")
            # Fallback: try to insert a dummy (safely) or just list if possible via information_schema
            # Since we are an agent, we can try to guess or use a generic RPC if CELTM has one, 
            # but usually Supabase doesn't expose information_schema easily via PostgREST without custom RPC.
            # We'll just report 'No data' and rely on our code audit.
    except Exception as e:
        print(f"Error accessing table: {e}")
