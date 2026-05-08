"""
Fire a real POST to /api/v1/profile/me/artifacts using a service-role JWT
to get the exact 500 traceback from the backend.
"""
import sys
from pathlib import Path
from io import BytesIO
import requests

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import get_settings
from app.integrations.supabase import get_supabase_client

settings = get_settings()
client = get_supabase_client(settings)

# Get an actual user to test with
users_res = client.auth.admin.list_users()
test_user = None
for u in users_res:
    if u.email == "e2e_tester@example.com":
        test_user = u
        break

if not test_user:
    print("e2e_tester user not found, picking first available user")
    test_user = users_res[0] if users_res else None

if not test_user:
    print("No users found! Cannot test.")
    sys.exit(1)

print(f"Testing with user: {test_user.email} (id={test_user.id})")

# Sign in as the e2e user to get a real JWT
try:
    sign_res = client.auth.sign_in_with_password({
        "email": "e2e_tester@example.com",
        "password": "Password123!",
    })
    user_token = sign_res.session.access_token
    print(f"Got user JWT (first 40 chars): {user_token[:40]}...")
except Exception as e:
    print("FATAL: Could not sign in as e2e_tester:", e)
    sys.exit(1)

API_URL = "http://127.0.0.1:8000/api/v1/profile/me/artifacts"

dummy_file = BytesIO(b"Name: QA Tester\nSkills: Python, Testing\nExperience: 3 years")
dummy_file.name = "test_resume.txt"

response = requests.post(
    API_URL,
    headers={"Authorization": f"Bearer {user_token}"},
    files={"file": ("test_resume.txt", dummy_file, "text/plain")},
    data={"file_type": "resume"},
    timeout=30,
)

print(f"\nResponse Status: {response.status_code}")
print(f"Response Headers: {dict(response.headers)}")
try:
    print(f"Response Body: {response.json()}")
except Exception:
    print(f"Response Text: {response.text}")
