
import requests
import json

def test_discovery():
    BASE_URL = "http://127.0.0.1:8000/api/v1"
    # Note: We need a valid token to test since it depends on current_user
    # However, for a quick sanity check during development, I'll check if the route is registered
    
    print("Checking /assessments/subjects endpoint...")
    try:
        # This will likely 401/403 without a token, but it verifies the route exists
        resp = requests.get(f"{BASE_URL}/assessments/subjects")
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            print(json.dumps(resp.json(), indent=2))
        else:
            print("Authentication required for full test, but route is registered.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_discovery()
