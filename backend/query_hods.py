import asyncio
from app.settings import get_settings
from app.database import Database

settings = get_settings()
db = Database(settings.database_target, postgres_schema=settings.postgres_schema)

if db.using_postgres:
    db._init_postgres()
    with db._get_postgres_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, email, name, role FROM celtm_app.admin_accounts WHERE role = 'institution_admin'")
            rows = cur.fetchall()
            for r in rows:
                print(r)
else:
    rows = db.query_all("SELECT id, email, name, role FROM admin_accounts WHERE role = 'institution_admin'")
    for r in rows:
        print(dict(r))
