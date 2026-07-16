from tests.e2e.conftest import auth_headers

ROOM_ID = 999999
TOKEN = "dummy-invite-token"


class TestInvitesUnauthenticated:
    def test_create_invite(self, test_client):
        assert test_client.post(f"/api/v1/rooms/{ROOM_ID}/invites").status_code == 401

    def test_validate_invite_is_public(self, test_client):
        # GET /invites/{token} has no auth dependency by design — unknown token is 404, not 401.
        assert test_client.get(f"/api/v1/invites/{TOKEN}").status_code == 404

    def test_accept_invite(self, test_client):
        assert test_client.post(f"/api/v1/invites/{TOKEN}/accept").status_code == 401

    def test_reject_invite(self, test_client):
        assert test_client.post(f"/api/v1/invites/{TOKEN}/reject").status_code == 401


class TestInvitesAuthenticated:
    def test_create_invite(self, test_client, make_user, make_room):
        admin = make_user("admin@example.com", profile="https://example.com/a.png")
        room = make_room(admin)

        r = test_client.post(f"/api/v1/rooms/{room['id']}/invites", headers=auth_headers(admin))
        assert r.status_code == 201
        body = r.json()
        assert body["room_id"] == room["id"]
        assert body["invited_by_email"] == admin["email"]
        assert body["invited_by_profile"] == admin["profile"]
        assert body["days_left"] == 7

    def test_create_invite_requires_admin(self, test_client, make_user, make_room, add_member):
        admin = make_user("admin2@example.com")
        member = make_user("member2@example.com")
        room = make_room(admin)
        add_member(room["id"], member)

        r = test_client.post(f"/api/v1/rooms/{room['id']}/invites", headers=auth_headers(member))
        assert r.status_code == 403

    def test_validate_invite(self, test_client, make_user, make_room):
        admin = make_user("admin3@example.com")
        room = make_room(admin)
        token = test_client.post(f"/api/v1/rooms/{room['id']}/invites", headers=auth_headers(admin)).json()["token"]

        r = test_client.get(f"/api/v1/invites/{token}")
        assert r.status_code == 200
        assert r.json()["room_id"] == room["id"]

    def test_validate_invite_unknown_token(self, test_client):
        r = test_client.get(f"/api/v1/invites/{TOKEN}")
        assert r.status_code == 404

    def test_accept_invite(self, test_client, make_user, make_room):
        admin = make_user("admin4@example.com")
        newcomer = make_user("newcomer4@example.com")
        room = make_room(admin)
        token = test_client.post(f"/api/v1/rooms/{room['id']}/invites", headers=auth_headers(admin)).json()["token"]

        r = test_client.post(f"/api/v1/invites/{token}/accept", headers=auth_headers(newcomer))
        assert r.status_code == 200
        assert r.json()["room_id"] == room["id"]

        members = test_client.get(f"/api/v1/rooms/{room['id']}/members", headers=auth_headers(admin)).json()
        assert any(m["email"] == newcomer["email"] for m in members)

    def test_accept_invite_idempotent_for_existing_member(self, test_client, make_user, make_room):
        admin = make_user("admin5@example.com")
        room = make_room(admin)
        token = test_client.post(f"/api/v1/rooms/{room['id']}/invites", headers=auth_headers(admin)).json()["token"]

        r = test_client.post(f"/api/v1/invites/{token}/accept", headers=auth_headers(admin))
        assert r.status_code == 200
        assert r.json()["message"] == "Already a member"

    def test_reject_invite(self, test_client, make_user, make_room):
        admin = make_user("admin6@example.com")
        room = make_room(admin)
        token = test_client.post(f"/api/v1/rooms/{room['id']}/invites", headers=auth_headers(admin)).json()["token"]

        r = test_client.post(f"/api/v1/invites/{token}/reject", headers=auth_headers(admin))
        assert r.status_code == 204

        follow_up = test_client.get(f"/api/v1/invites/{token}")
        assert follow_up.status_code == 410

    def test_reject_invite_unknown_token(self, test_client, make_user):
        user = make_user("u7@example.com")
        r = test_client.post(f"/api/v1/invites/{TOKEN}/reject", headers=auth_headers(user))
        assert r.status_code == 404
