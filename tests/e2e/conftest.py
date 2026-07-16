import os
from typing import Generator

import pytest
from sqlalchemy import Connection, create_engine
from fastapi.testclient import TestClient

from app.utils.jwt_utils import create_jwt
from app.models.auth.auth_model import upsert_user
from app.models.rooms.rooms_model import insert_room, insert_user_room
from app.models.expenses.expenses_model import insert_expense
from db.engine import db_conn
from db.redis_client import redis_conn
from main import app


class FakeRedis:
    """In-memory stand-in for redis.Redis, supporting only the get/setex/delete
    calls used by the auth cache — keeps e2e tests from needing a live Redis."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = value

    def delete(self, *keys: str) -> None:
        for key in keys:
            self._store.pop(key, None)


def _get_test_db_url() -> str:
    return (
        f"postgresql://{os.environ['TEST_DB_USER']}:{os.environ['TEST_DB_PASSWORD']}"
        f"@{os.environ['TEST_DB_HOST']}:{os.environ['TEST_DB_PORT']}/{os.environ['TEST_DB_NAME']}"
    )


@pytest.fixture(scope="session")
def db_engine():
    required = ["TEST_DB_NAME", "TEST_DB_HOST", "TEST_DB_PORT", "TEST_DB_USER", "TEST_DB_PASSWORD"]
    missing = [k for k in required if k not in os.environ]
    if missing:
        raise RuntimeError(
            f"Missing test DB env vars: {', '.join(missing)}. "
            "Run `docker compose -f docker-compose.test.yml up -d` and "
            "`scripts/sync_test_schema.sh`, then set TEST_DB_* in .env."
        )
    engine = create_engine(_get_test_db_url())
    yield engine
    engine.dispose()


@pytest.fixture
def conn(db_engine) -> Generator[Connection, None, None]:
    """A connection wrapped in a transaction that is always rolled back —
    every test gets an isolated view of the schema with no manual cleanup."""
    connection = db_engine.connect()
    transaction = connection.begin()
    try:
        yield connection
    finally:
        transaction.rollback()
        connection.close()


@pytest.fixture
def test_client(conn) -> Generator[TestClient, None, None]:
    def _override_db_conn():
        yield conn

    def _override_redis_conn():
        yield FakeRedis()

    app.dependency_overrides[db_conn] = _override_db_conn
    app.dependency_overrides[redis_conn] = _override_redis_conn
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(db_conn, None)
    app.dependency_overrides.pop(redis_conn, None)


def auth_headers(user: dict) -> dict[str, str]:
    token = create_jwt(user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def make_user(conn):
    def _make_user(email: str, name: str | None = "Test User", profile: str | None = None) -> dict:
        return upsert_user(conn, uid=f"uid-{email}", email=email, name=name, profile=profile)

    return _make_user


@pytest.fixture
def make_room(conn):
    def _make_room(admin_user: dict) -> dict:
        room = insert_room(conn)
        insert_user_room(conn, admin_user["id"], room["id"], role="Admin")
        return room

    return _make_room


@pytest.fixture
def add_member(conn):
    def _add_member(room_id: int, user: dict, role: str = "Member") -> None:
        insert_user_room(conn, user["id"], room_id, role=role)

    return _add_member


@pytest.fixture
def make_expense(conn):
    def _make_expense(room_id: int, user_email: str, money: float = 10.0, material: str = "test item") -> dict:
        return insert_expense(conn, room_id, user_email, material, money)

    return _make_expense
