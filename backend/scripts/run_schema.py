import os
import psycopg2
from dotenv import load_dotenv

def main():
    load_dotenv()
    db_string = os.getenv("SUPABASE_DB_CONNECTION_STRING")
    if not db_string:
        print("SUPABASE_DB_CONNECTION_STRING not found in .env")
        return

    schema_file = os.path.join(os.path.dirname(__file__), "..", "sql", "reset_schema.sql")
    if not os.path.exists(schema_file):
        print(f"Schema file not found at {schema_file}")
        return

    with open(schema_file, 'r', encoding='utf-8') as f:
        sql = f.read()

    try:
        conn = psycopg2.connect(db_string)
        conn.autocommit = True
        with conn.cursor() as cur:
            print("Executing reset_schema.sql...")
            cur.execute(sql)
            print("Schema execution successful.")
    except Exception as e:
        print(f"Error executing schema: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    main()
