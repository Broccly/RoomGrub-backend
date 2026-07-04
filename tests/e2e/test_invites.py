from tests.e2e.conftest import _auth_headers

ROOM_ID = 999999
TOKEN = "dummy-invite-token"


class TestInvitesUnauthenticated:
    def test_create_invite(self, test_client):
        assert test_client.post(f"/api/v1/rooms/{ROOM_ID}/invites").status_code == 401

    def test_validate_invite(self, test_client):
        assert test_client.get(f"/api/v1/invites/{TOKEN}").status_code == 401

    def test_accept_invite(self, test_client):
        assert test_client.post(f"/api/v1/invites/{TOKEN}/accept").status_code == 401

    def test_reject_invite(self, test_client):
        assert test_client.post(f"/api/v1/invites/{TOKEN}/reject").status_code == 401


class TestInvitesAuthenticated:
    def test_create_invite(self, test_client):
        r = test_client.post(f"/api/v1/rooms/{ROOM_ID}/invites", headers=_auth_headers())
        assert r.status_code != 401

    def test_validate_invite(self, test_client):
        r = test_client.get(f"/api/v1/invites/{TOKEN}", headers=_auth_headers())
        assert r.status_code != 401

    def test_accept_invite(self, test_client):
        r = test_client.post(f"/api/v1/invites/{TOKEN}/accept", headers=_auth_headers())
        assert r.status_code != 401

    def test_reject_invite(self, test_client):
        r = test_client.post(f"/api/v1/invites/{TOKEN}/reject", headers=_auth_headers())
        assert r.status_code != 401
