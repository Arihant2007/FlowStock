import os
import sys
from sqlalchemy import text
from app.infrastructure.database import SessionLocal

db = SessionLocal()
try:
    result = db.execute(text("SELECT id, username, failed_login_count, version, locked_until FROM users")).fetchall()
    for row in result:
        print(row)
except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    db.close()
