"""Pytest fixtures: an isolated in-memory database and an authenticated client."""
from __future__ import annotations

import os

# Use an isolated SQLite database for tests before importing the app.
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_systemiq.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("ENVIRONMENT", "test")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core import database
from app.core.config import settings
from app.core.database import Base, get_db
from app.main import create_app


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(
        settings.DATABASE_URL, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)


@pytest.fixture()
def db_session(engine):
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(engine, monkeypatch):
    """A TestClient with the DB dependency overridden and background tasks off."""
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    # Disable background loops during tests.
    async def _noop():
        return None

    from app.services.background import background_manager

    monkeypatch.setattr(background_manager, "start", _noop)
    monkeypatch.setattr(background_manager, "stop", _noop)

    app = create_app()

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def admin_token(client):
    """Log in as the bootstrap admin created on startup."""
    resp = client.post(
        "/api/v1/auth/login/json",
        json={"username": settings.FIRST_ADMIN_USERNAME, "password": settings.FIRST_ADMIN_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture()
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}
