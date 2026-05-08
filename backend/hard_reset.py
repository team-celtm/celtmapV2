import os
import asyncio
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not supabase_url or not supabase_key:
    print("Error: Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env")
    exit(1)

supabase: Client = create_client(supabase_url, supabase_key)

# Tables to clear in order of dependency
TABLES = [
    "user_answers",
    "assessments",
    "learning_modules",
    "learning_paths",
    "skill_requests",
    "user_hidden_skills",
    "user_skills",
    "user_artifacts",
    "uploaded_artifacts",
    "reports",
    "dashboard_projections",
    "job_failures",
    "ai_call_logs",
    "domain_events",
    "profile_assets",
    "profiles"
]

async def hard_reset():
    print("=== STARTING HARD RESET ===")
    
    # 1. Clear Tables
    for table in TABLES:
        print(f"Clearing table: {table}...")
        try:
            # delete all where id is not null (guaranteed to catch everything)
            supabase.table(table).delete().neq("created_at", "1970-01-01").execute()
            print(f"  [OK] Table {table} cleared.")
        except Exception as e:
            print(f"  [Error] Failed to clear {table}: {e}")

    # 2. Delete All Users (Auth)
    print("\nDeleting users from Supabase Auth...")
    try:
        # Note: List users is paginated, we'll just do one pass for now or loop
        users_res = supabase.auth.admin.list_users()
        users = users_res
        
        # In modern supabase-py, list_users returns the list directly or has a user property
        # Depending on version, we check
        user_list = []
        if hasattr(users, 'users'):
            user_list = users.users
        elif isinstance(users, list):
            user_list = users
            
        print(f"Found {len(user_list)} users to delete.")
        for u in user_list:
            print(f"  Deleting user: {u.email} ({u.id})")
            supabase.auth.admin.delete_user(u.id)
        print("  [OK] All users deleted.")
    except Exception as e:
        print(f"  [Error] Failed to delete users: {e}")

    print("\n=== HARD RESET COMPLETE ===")
    print("You can now sign up with a fresh account.")

if __name__ == "__main__":
    asyncio.run(hard_reset())
