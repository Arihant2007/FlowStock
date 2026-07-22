import os
from alembic.config import Config
from alembic import command
from dotenv import load_dotenv

load_dotenv()

conn_str = os.getenv("DATABASE_URL")
if conn_str.startswith("postgresql://"):
    # replace the database name (neondb) with audit_test_db
    # It looks like: postgresql://neondb_owner:npg_zo3RAkMyT4em@ep-still-mouse-azzhjw0y-pooler.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
    # We'll split on '/' and '?'
    parts = conn_str.split('?')
    base_url = parts[0]
    base_parts = base_url.rsplit('/', 1)
    new_base_url = base_parts[0] + "/audit_test_db"
    new_conn_str = new_base_url
    if len(parts) > 1:
        new_conn_str += "?" + parts[1]
    
    os.environ["DATABASE_URL"] = new_conn_str

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", new_conn_str)

    print(f"Running migrations on {new_conn_str}...")
    try:
        command.upgrade(alembic_cfg, "head")
        print("Migrations successful on clean database.")
    except Exception as e:
        print(f"Migration failed: {e}")
