import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import Database
from app.settings import get_settings

def test():
    settings = get_settings()
    print("Testing DB connection...")
    db = Database(settings.database_target, postgres_schema=settings.postgres_schema)
    try:
        db.init()
        print("DB initialized successfully.")
    except Exception as e:
        print(f"Error initializing DB: {e}")

if __name__ == "__main__":
    test()
