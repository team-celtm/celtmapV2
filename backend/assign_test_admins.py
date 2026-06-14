import sys
from pathlib import Path
from app.settings import get_settings
from app.database import Database, now_iso

def main():
    settings = get_settings()
    db = Database(settings.database_path)

    print(f"Connecting to database at {settings.database_path}")

    # Get CELTM Demo Institute
    inst = db.query_one("SELECT * FROM institutions WHERE name = 'CELTM Demo Institute'")
    if not inst:
        print("Error: CELTM Demo Institute not found in database.")
        sys.exit(1)

    # Get Department
    dept = db.query_one("SELECT * FROM departments WHERE institution_id = ? AND name = 'AI and Data Science'", (inst["id"],))
    if not dept:
        print("Error: Department 'AI and Data Science' not found in database.")
        sys.exit(1)

    # Update all profiles
    profiles = db.query_all("SELECT * FROM profiles")
    count = 0
    for profile in profiles:
        db.execute(
            """
            UPDATE profiles
            SET institution_id = ?,
                department_id = ?,
                institution_name = ?,
                department_name = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (inst["id"], dept["id"], inst["name"], dept["name"], now_iso(), profile["id"])
        )
        count += 1

    print(f"Successfully assigned {count} users to CELTM Demo Institute.")

if __name__ == "__main__":
    main()
