import json

from app.services.auth import auth_services


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
