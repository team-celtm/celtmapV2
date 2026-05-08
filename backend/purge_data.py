import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not supabase_url or not supabase_key:
    print("Missing credentials")
    exit(1)

supabase: Client = create_client(supabase_url, supabase_key)

# Ordered for foreign keys (approximate)
tables_to_clear = [
    "user_answers",
    "assessments",
    "learning_modules",
    "learning_paths",
    "skill_requests",
    "user_hidden_skills",
    "user_skills",
    "user_artifacts",
    "reports",
    "dashboard_projections",
    "trajectory_roles",
    "profiles",
    "users"
]

def purge_all():
    print("--- Starting Corrected Purge ---")
    for table in tables_to_clear:
        print(f"Clearing table: {table}")
        try:
            # Delete all rows
            # Using a filter that is always true for user data (id/user_id exists)
            res = supabase.table(table).delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
            print(f"Cleared {table}")
        except Exception as e:
            # Try user_id if id fails
            try:
                 res = supabase.table(table).delete().neq("user_id", "00000000-0000-0000-0000-000000000000").execute()
                 print(f"Cleared {table} (using user_id)")
            except Exception as e2:
                print(f"Error clearing {table}: {e2}")
    
    print("--- Purge Complete ---")

if __name__ == "__main__":
    purge_all()
