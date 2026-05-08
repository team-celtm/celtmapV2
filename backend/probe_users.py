"""
Probe the actual DB state to find what would cause a 500 for a real browser user.
Specifically checks: users table, profile sync, and mimics what upload_artifact does.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import get_settings
from app.integrations.supabase import get_supabase_client

settings = get_settings()
client = get_supabase_client(settings)

# 1. List all users in auth
print("=== AUTH USERS ===")
users_res = client.auth.admin.list_users()
for u in users_res:
    print(f"  email={u.email}  id={u.id}")

# 2. List users in public.users table
print("\n=== public.users TABLE ===")
try:
    res = client.table("users").select("id,email,full_name,role").execute()
    if res.data:
        for row in res.data:
            print(f"  id={row.get('id')}  email={row.get('email')}  role={row.get('role')}")
    else:
        print("  (empty)")
except Exception as e:
    print("  ERROR querying users table:", e)

# 3. List users in public.profiles table
print("\n=== public.profiles TABLE ===")
try:
    res = client.table("profiles").select("id,email,full_name").execute()
    if res.data:
        for row in res.data:
            print(f"  id={row.get('id')}  email={row.get('email')}")
    else:
        print("  (empty)")
except Exception as e:
    print("  ERROR querying profiles table:", e)

# 4. Find real user who might be hitting the 500
print("\n=== REAL USER PROBE ===")
for u in users_res:
    if u.email != "e2e_tester@example.com":
        print(f"Real user found: {u.email}  id={u.id}")
        
        # Try to upsert this user into public.users (simulates _sync_legacy_user_record)
        import datetime, timezone as tz
        from datetime import timezone
        now = datetime.datetime.now(timezone.utc).isoformat()
        try:
            payload = {
                "id": str(u.id),
                "email": u.email,
                "full_name": u.user_metadata.get("full_name") or u.user_metadata.get("name") or "",
                "role": None,  # This is what the service sends for a new user with no headline
                "target_role_id": None,
                "avatar_url": None,
                "created_at": now,
                "updated_at": now,
            }
            print(f"  Attempting upsert payload: {payload}")
            res = client.table("users").upsert(payload, on_conflict="id").execute()
            print(f"  Upsert result: {res.data}")
        except Exception as exc:
            print(f"  UPSERT FAILED: {exc}")
        break
