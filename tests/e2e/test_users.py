from tests.e2e.conftest import auth_headers

GOOGLE_PHOTO = "https://lh3.googleusercontent.com/a/photo.png"


class TestUsersUnauthenticated:
    def test_get_me(self, test_client):
        assert test_client.get("/api/v1/users/me").status_code == 401

    def test_update_me(self, test_client):
        assert test_client.patch("/api/v1/users/me", json={"name": "X"}).status_code == 401


class TestGetMe:
    def test_returns_profile_and_type(self, test_client, make_user):
        user = make_user("me@example.com", name="Me", profile=GOOGLE_PHOTO)
        r = test_client.get("/api/v1/users/me", headers=auth_headers(user))
        assert r.status_code == 200
        assert r.json() == {
            "id": user["id"],
            "email": "me@example.com",
            "name": "Me",
            "profile": GOOGLE_PHOTO,
            "type": "registered",
        }


class TestUpdateMe:
    def test_update_name(self, test_client, make_user):
        user = make_user("rename-me@example.com", name="Old", profile=GOOGLE_PHOTO)
        r = test_client.patch("/api/v1/users/me", json={"name": "  New Name  "}, headers=auth_headers(user))
        assert r.status_code == 200
        assert r.json()["name"] == "New Name"
        assert r.json()["profile"] == GOOGLE_PHOTO

    def test_update_avatar(self, test_client, make_user, monkeypatch):
        monkeypatch.setenv("AVATAR_ALLOWED_HOSTS", "avatars.roomgrub.app")
        user = make_user("avatar-me@example.com", name="Me")
        url = "https://avatars.roomgrub.app/u/1.png"

        r = test_client.patch("/api/v1/users/me", json={"avatar": url}, headers=auth_headers(user))
        assert r.status_code == 200
        assert r.json()["profile"] == url
        assert r.json()["name"] == "Me"

    def test_update_both(self, test_client, make_user):
        user = make_user("both-me@example.com", name="Me")
        r = test_client.patch(
            "/api/v1/users/me", json={"name": "Both", "avatar": GOOGLE_PHOTO}, headers=auth_headers(user)
        )
        assert r.status_code == 200
        assert (r.json()["name"], r.json()["profile"]) == ("Both", GOOGLE_PHOTO)

    def test_null_avatar_removes_it(self, test_client, make_user):
        user = make_user("clear-me@example.com", name="Me", profile=GOOGLE_PHOTO)
        r = test_client.patch("/api/v1/users/me", json={"avatar": None}, headers=auth_headers(user))
        assert r.status_code == 200
        assert r.json()["profile"] is None

    def test_empty_body_is_400(self, test_client, make_user):
        user = make_user("empty-me@example.com")
        r = test_client.patch("/api/v1/users/me", json={}, headers=auth_headers(user))
        assert r.status_code == 400

    def test_invalid_names_are_422(self, test_client, make_user):
        user = make_user("bad-name-me@example.com")
        for name in [None, "", "   ", "x" * 51]:
            r = test_client.patch("/api/v1/users/me", json={"name": name}, headers=auth_headers(user))
            assert r.status_code == 422, name

    def test_invalid_avatars_are_400(self, test_client, make_user):
        user = make_user("bad-avatar-me@example.com", profile=GOOGLE_PHOTO)
        for avatar in [
            "http://lh3.googleusercontent.com/a/photo.png",
            "https://evil.example.com/a.png",
            "not a url",
            "https://lh3.googleusercontent.com/" + "a" * 2048,
        ]:
            r = test_client.patch("/api/v1/users/me", json={"avatar": avatar}, headers=auth_headers(user))
            assert r.status_code == 400, avatar
        assert test_client.get("/api/v1/users/me", headers=auth_headers(user)).json()["profile"] == GOOGLE_PHOTO

    def test_edit_invalidates_cache_and_shows_in_room(self, test_client, make_user, make_room, fake_redis):
        user = make_user("cache-me@example.com", name="Before")
        room = make_room(user)
        headers = auth_headers(user)
        # Any authenticated request fills the auth:user cache.
        test_client.get("/api/v1/rooms", headers=headers)
        assert fake_redis.get(f"auth:user:{user['id']}") is not None

        test_client.patch("/api/v1/users/me", json={"name": "After"}, headers=headers)

        assert fake_redis.get(f"auth:user:{user['id']}") is None
        members = test_client.get(f"/api/v1/rooms/{room['id']}/members", headers=headers).json()
        assert members[0]["name"] == "After"
