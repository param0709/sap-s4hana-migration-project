"""Shared test fixtures.

Tests run against an isolated in-memory SQLite database so the suite needs no
running PostgreSQL instance. Production and Docker Compose both use PostgreSQL.
"""
import io
import os
import tempfile

import pytest

# Assigned directly, not with setdefault: an ambient DATABASE_URL from a shell
# or .env file must never let the suite touch a real database or storage tree.
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["STORAGE_DIR"] = tempfile.mkdtemp(prefix="copilot-test-storage-")

import pandas as pd  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import Base, get_db  # noqa: E402
import app.models as _models
from app.main import app


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def project(client):
    """A saved project the upload tests can attach files to."""
    response = client.post(
        f"{settings.api_prefix}/projects",
        json={"project_name": "Customer Master Wave 1", "client_name": "Northwind India"},
    )
    assert response.status_code == 201
    return response.json()


def make_xlsx(frame: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    frame.to_excel(buffer, index=False)
    return buffer.getvalue()


@pytest.fixture()
def valid_ecc_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "KUNNR": ["00001001", "00001002"],
            "NAME1": ["Alpha Traders Pvt Ltd", "Beta Exports"],
            "ORT01": ["Mumbai", "Pune"],
            "LAND1": ["IN", "IN"],
            "KTOKD": ["ZDOM", "ZDOM"],
            "BUKRS": ["1000", "1000"],
            "STCD3": ["27ABCDE1234F1Z5", ""],
            "SMTP_ADDR": ["sales@alpha.in", "info@beta.in"],
        }
    )
