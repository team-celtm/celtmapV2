import asyncio
import os
from supabase import create_client

supabase_url = os.environ.get("SUPABASE_URL", "https://clkocfoxzfmxdsxdmdfr.supabase.co")
supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNsa29jZm94emZteGRzeGRtZGZyIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTYyODA0NywiZXhwIjoyMDkxMjA0MDQ3fQ.G48UUaJzFBa5LU3wGd_0Xb7-40LLtgLTzbpK-RvAw54")
supabase = create_client(supabase_url, supabase_key)

try:
    print("Creating user e2e_tester@example.com...")
    res = supabase.auth.admin.create_user({
        "email": "e2e_tester@example.com",
        "password": "Password123!",
        "email_confirm": True
    })
    print("User created:", res)
except Exception as e:
    print("Error creating user (might already exist):", e)
    
    # Let's try to update the password if it exists
    print("Attempting to update password...")
    try:
        users = supabase.auth.admin.list_users()
        user = next((u for u in users if u.email == "e2e_tester@example.com"), None)
        if user:
            supabase.auth.admin.update_user_by_id(user.id, {"password": "Password123!"})
            print("Password updated!")
    except Exception as e2:
        print("Error updating password:", e2)

print("Done.")
