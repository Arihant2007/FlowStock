import os
from alembic.config import Config
from alembic import command

# Point to a temporary local SQLite db
os.environ["DATABASE_URL"] = "sqlite:///test_clean.db"

alembic_cfg = Config("alembic.ini")
alembic_cfg.set_main_option("sqlalchemy.url", "sqlite:///test_clean.db")

print("Running migrations on clean SQLite database...")
try:
    command.upgrade(alembic_cfg, "head")
    print("Migrations successful on clean database.")
except Exception as e:
    print(f"Migration failed: {e}")
