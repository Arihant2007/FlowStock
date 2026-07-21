import sys
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.domains.auth.repository import _user_with_role_stmt

engine = create_engine("sqlite:///:memory:")
from app.infrastructure.base_model import Base
Base.metadata.create_all(engine)

SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

try:
    print("Executing query...")
    stmt = _user_with_role_stmt()
    db.scalar(stmt)
    print("Query executed successfully.")
except Exception as e:
    import traceback
    traceback.print_exc()
