import json
import time

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.services.auth import auth_services
from app.utils.jwt_utils import hash_refresh_token
from db.engine import db_conn
from db.redis_client import redis_conn
from main import app

REFRESH_URL = "/api/v1/auth/refresh"
LOGOUT_URL = "/api/v1/auth/logout"


@pytest.fixture
def login(test_client, monkeypatch):
    def _login(email: str = "device@example.com", client: TestClient = test_client) -> dict:
        monkeypatch.setattr(
            auth_services,
            "verify_provider_token",
            lambda provider, token: {"email": email, "name": "Device User", "picture": None},
        )
        r = client.post("/api/v1/auth/login", json={"provider": "google", "token": "valid-token"})
        assert r.status_code == 200
        return r.json()

    return _login


@pytest.fixture
def rollback_on_error_client(conn, fake_redis):
    """A client whose db dependency behaves like the real db_conn(): work done by a
    request that errors is rolled back (here to a savepoint, so the test's own
    transaction survives)."""

    def _db_conn():
        savepoint = conn.begin_nested()
        try:
            yield conn
        except Exception:
            savepoint.rollback()
            raise
        savepoint.commit()

    def _redis_conn():
        yield fake_redis

    app.dependency_overrides[db_conn] = _db_conn
    app.dependency_overrides[redis_conn] = _redis_conn
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(db_conn, None)
    app.dependency_overrides.pop(redis_conn, None)


def _spend_long_ago(conn, refresh_token: str) -> None:
    conn.execute(
        text("UPDATE refresh_tokens SET used_at = used_at - interval '5 minutes' WHERE token_hash = :h"),
        {"h": hash_refresh_token(refresh_token)},
    )


class TestAuth:
    def test_login_unknown_provider(self, test_client):
        r = test_client.post("/api/v1/auth/login", json={"provider": "twitter", "token": "abc"})
        assert r.status_code == 400

    def test_login_creates_and_returns_user(self, test_client, monkeypatch, fake_redis):
        monkeypatch.setattr(
            auth_services,
            "verify_provider_token",
            lambda provider, token: {
                "email": "newuser@example.com",
                "name": "New User",
                "picture": "https://example.com/p.png",
            },
        )

        r = test_client.post("/api/v1/auth/login", json={"provider": "google", "token": "valid-token"})
        assert r.status_code == 200
        body = r.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]
        assert body["user"]["email"] == "newuser@example.com"
        assert body["user"]["name"] == "New User"
        assert body["user"]["profile"] == "https://example.com/p.png"

        events = fake_redis.streams.get("rg:emails", [])
        assert len(events) == 1
        assert events[0]["type"] == "welcome"
        payload = json.loads(events[0]["payload"])
        assert payload == {"email": "newuser@example.com", "name": "New User"}

    def test_login_upserts_existing_user_by_email(self, test_client, monkeypatch, make_user, fake_redis):
        existing = make_user("existing@example.com", name="Old Name", profile=None)

        monkeypatch.setattr(
            auth_services,
            "verify_provider_token",
            lambda provider, token: {
                "email": "existing@example.com",
                "name": "Updated Name",
                "picture": "https://example.com/updated.png",
            },
        )

        r = test_client.post("/api/v1/auth/login", json={"provider": "google", "token": "valid-token"})
        assert r.status_code == 200
        body = r.json()
        assert body["user"]["id"] == existing["id"]
        assert body["user"]["name"] == "Updated Name"
        assert body["user"]["profile"] == "https://example.com/updated.png"

        assert fake_redis.streams.get("rg:emails", []) == []


class TestRefreshTokens:
    def test_login_returns_both_tokens(self, login, conn):
        body = login()
        assert body["refresh_token"]
        assert body["expires_in"] == 15 * 60

        rows = conn.execute(
            text("SELECT token_hash FROM refresh_tokens WHERE user_id = :id"), {"id": body["user"]["id"]}
        ).fetchall()
        # Only the hash is stored, never the token itself.
        assert [r.token_hash for r in rows] == [hash_refresh_token(body["refresh_token"])]

    def test_access_token_is_short_lived(self, login):
        body = login()
        claims = jwt.decode(body["access_token"], options={"verify_signature": False})
        assert claims["sub"] == str(body["user"]["id"])
        assert 0 < claims["exp"] - time.time() <= 15 * 60

    def test_refresh_rotates_and_new_tokens_work(self, login, test_client):
        first = login()

        r = test_client.post(REFRESH_URL, json={"refresh_token": first["refresh_token"]})
        assert r.status_code == 200
        second = r.json()
        assert second["token_type"] == "bearer"
        assert second["expires_in"] == 15 * 60
        assert second["refresh_token"] != first["refresh_token"]
        assert "user" not in second

        rooms = test_client.get("/api/v1/rooms", headers={"Authorization": f"Bearer {second['access_token']}"})
        assert rooms.status_code == 200

        r = test_client.post(REFRESH_URL, json={"refresh_token": second["refresh_token"]})
        assert r.status_code == 200

    def test_refresh_extends_the_idle_window(self, login, test_client, conn):
        first = login()
        # The token is about to expire...
        conn.execute(
            text("UPDATE refresh_tokens SET expires_at = now() + interval '1 hour' WHERE token_hash = :h"),
            {"h": hash_refresh_token(first["refresh_token"])},
        )
        second = test_client.post(REFRESH_URL, json={"refresh_token": first["refresh_token"]}).json()

        # ...but using it yields one with a full lifetime again.
        days_left = conn.execute(
            text("SELECT extract(epoch FROM expires_at - now()) / 86400 FROM refresh_tokens WHERE token_hash = :h"),
            {"h": hash_refresh_token(second["refresh_token"])},
        ).scalar_one()
        assert 89 < days_left <= 90.1

    def test_spent_token_inside_grace_window_succeeds(self, login, test_client):
        first = login()
        second = test_client.post(REFRESH_URL, json={"refresh_token": first["refresh_token"]}).json()

        retry = test_client.post(REFRESH_URL, json={"refresh_token": first["refresh_token"]})
        assert retry.status_code == 200

        # The family is intact: both tokens issued for the spent one still work.
        assert test_client.post(REFRESH_URL, json={"refresh_token": second["refresh_token"]}).status_code == 200
        assert test_client.post(REFRESH_URL, json={"refresh_token": retry.json()["refresh_token"]}).status_code == 200

    def test_spent_token_past_grace_window_revokes_family(self, login, test_client, conn):
        first = login()
        second = test_client.post(REFRESH_URL, json={"refresh_token": first["refresh_token"]}).json()
        _spend_long_ago(conn, first["refresh_token"])

        replay = test_client.post(REFRESH_URL, json={"refresh_token": first["refresh_token"]})
        assert replay.status_code == 401
        assert replay.json() == {"detail": "Invalid refresh token"}

        # The legitimate holder of the newer token is signed out too.
        r = test_client.post(REFRESH_URL, json={"refresh_token": second["refresh_token"]})
        assert r.status_code == 401

    def test_family_revocation_survives_the_401(self, login, rollback_on_error_client, conn):
        client = rollback_on_error_client
        first = login(client=client)
        second = client.post(REFRESH_URL, json={"refresh_token": first["refresh_token"]}).json()
        _spend_long_ago(conn, first["refresh_token"])

        assert client.post(REFRESH_URL, json={"refresh_token": first["refresh_token"]}).status_code == 401

        live = conn.execute(
            text("SELECT count(*) FROM refresh_tokens WHERE user_id = :id AND revoked_at IS NULL"),
            {"id": first["user"]["id"]},
        ).scalar_one()
        assert live == 0
        assert client.post(REFRESH_URL, json={"refresh_token": second["refresh_token"]}).status_code == 401

    def test_reuse_on_one_device_leaves_other_devices_signed_in(self, login, test_client, conn):
        phone = login()
        laptop = login()
        test_client.post(REFRESH_URL, json={"refresh_token": phone["refresh_token"]})
        _spend_long_ago(conn, phone["refresh_token"])
        assert test_client.post(REFRESH_URL, json={"refresh_token": phone["refresh_token"]}).status_code == 401

        assert test_client.post(REFRESH_URL, json={"refresh_token": laptop["refresh_token"]}).status_code == 200

    def test_expired_token_rejected(self, login, test_client, conn):
        body = login()
        conn.execute(
            text("UPDATE refresh_tokens SET expires_at = now() - interval '1 day' WHERE token_hash = :h"),
            {"h": hash_refresh_token(body["refresh_token"])},
        )
        r = test_client.post(REFRESH_URL, json={"refresh_token": body["refresh_token"]})
        assert r.status_code == 401

    def test_unknown_token_rejected(self, test_client):
        r = test_client.post(REFRESH_URL, json={"refresh_token": "not-a-real-token"})
        assert r.status_code == 401
        assert r.json() == {"detail": "Invalid refresh token"}

    def test_access_token_is_not_a_refresh_token(self, login, test_client):
        body = login()
        r = test_client.post(REFRESH_URL, json={"refresh_token": body["access_token"]})
        assert r.status_code == 401

    def test_refresh_token_does_not_authenticate_requests(self, login, test_client):
        body = login()
        r = test_client.get("/api/v1/rooms", headers={"Authorization": f"Bearer {body['refresh_token']}"})
        assert r.status_code == 401

    def test_logout_revokes_and_is_idempotent(self, login, test_client):
        first = login()
        second = test_client.post(REFRESH_URL, json={"refresh_token": first["refresh_token"]}).json()

        assert test_client.post(LOGOUT_URL, json={"refresh_token": second["refresh_token"]}).status_code == 204
        assert test_client.post(REFRESH_URL, json={"refresh_token": second["refresh_token"]}).status_code == 401

        assert test_client.post(LOGOUT_URL, json={"refresh_token": second["refresh_token"]}).status_code == 204
        assert test_client.post(LOGOUT_URL, json={"refresh_token": "not-a-real-token"}).status_code == 204

    def test_logout_only_signs_out_that_device(self, login, test_client):
        phone = login()
        laptop = login()
        assert test_client.post(LOGOUT_URL, json={"refresh_token": phone["refresh_token"]}).status_code == 204

        assert test_client.post(REFRESH_URL, json={"refresh_token": phone["refresh_token"]}).status_code == 401
        assert test_client.post(REFRESH_URL, json={"refresh_token": laptop["refresh_token"]}).status_code == 200

    def test_login_cleans_up_dead_tokens_but_keeps_spent_ones(self, login, test_client, conn):
        expired = login()
        logged_out = login()
        spent = login()
        conn.execute(
            text("UPDATE refresh_tokens SET expires_at = now() - interval '1 day' WHERE token_hash = :h"),
            {"h": hash_refresh_token(expired["refresh_token"])},
        )
        test_client.post(LOGOUT_URL, json={"refresh_token": logged_out["refresh_token"]})
        rotated = test_client.post(REFRESH_URL, json={"refresh_token": spent["refresh_token"]}).json()

        latest = login()

        hashes = {
            r.token_hash
            for r in conn.execute(
                text("SELECT token_hash FROM refresh_tokens WHERE user_id = :id"), {"id": latest["user"]["id"]}
            )
        }
        assert hashes == {
            hash_refresh_token(spent["refresh_token"]),
            hash_refresh_token(rotated["refresh_token"]),
            hash_refresh_token(latest["refresh_token"]),
        }

    def test_deleting_user_removes_their_tokens(self, login, conn):
        body = login()
        conn.execute(text('DELETE FROM "Users" WHERE id = :id'), {"id": body["user"]["id"]})

        remaining = conn.execute(
            text("SELECT count(*) FROM refresh_tokens WHERE user_id = :id"), {"id": body["user"]["id"]}
        ).scalar_one()
        assert remaining == 0
