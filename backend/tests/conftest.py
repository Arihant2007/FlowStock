import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.infrastructure.base_model import Base
from app.infrastructure.database import get_db
from app.main import app

# By default, use sqlite for fast local tests if no DB URL is provided.
TEST_DB_URL = os.environ.get("DATABASE_URL", "sqlite:///:memory:")
IS_POSTGRES = TEST_DB_URL.startswith("postgresql")


@pytest.fixture(scope="session")
def engine_fixture():
    """Create a test engine.

    If using SQLite, we create all tables. If Postgres, we assume Alembic
    or the test runner has set up the schema. (For simplicity in this scaffold,
    we'll create_all for Postgres too if we want a fully fresh isolated DB,
    but usually you'd run alembic). Let's use create_all for simplicity.
    """
    engine = create_engine(TEST_DB_URL, echo=False)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db(engine_fixture) -> Generator[Session, None, None]:
    """Provide a transactional session per test.

    The transaction is rolled back after each test so tests don't leak state.
    """
    connection = engine_fixture.connect()
    transaction = connection.begin()

    session = Session(bind=connection)

    # Bind factory boy
    from tests.factories.users import RoleFactory, UserFactory

    UserFactory._meta.sqlalchemy_session = session
    RoleFactory._meta.sqlalchemy_session = session

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with the DB dependency overridden to our test transaction."""

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "postgres: mark test to run only when connected to PostgreSQL"
    )


def pytest_collection_modifyitems(config, items):
    if IS_POSTGRES:
        # Postgres is available, no need to skip postgres tests.
        return

    skip_pg = pytest.mark.skip(
        reason="Needs PostgreSQL (DATABASE_URL=postgresql://...)"
    )
    for item in items:
        if "postgres" in item.keywords:
            item.add_marker(skip_pg)
