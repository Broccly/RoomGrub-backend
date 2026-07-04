from tests.e2e.conftest import _auth_headers

ROOM_ID = 999999
MEMBER_ID = 999999


class TestMembersUnauthenticated:
    def test_list_members(self, test_client):
        assert test_client.get(f"/api/v1/rooms/{ROOM_ID}/members").status_code == 401

    def test_get_member_detail(self, test_client):
        assert test_client.get(f"/api/v1/rooms/{ROOM_ID}/members/{MEMBER_ID}").status_code == 401

    def test_update_member_role(self, test_client):
        assert test_client.patch(f"/api/v1/rooms/{ROOM_ID}/members/{MEMBER_ID}/role", json={"role": "member"}).status_code == 401

    def test_exit_room(self, test_client):
        assert test_client.delete(f"/api/v1/rooms/{ROOM_ID}/members/me").status_code == 401

    def test_remove_member(self, test_client):
        assert test_client.delete(f"/api/v1/rooms/{ROOM_ID}/members/{MEMBER_ID}").status_code == 401

    def test_settle_member(self, test_client):
        assert test_client.post(f"/api/v1/rooms/{ROOM_ID}/members/{MEMBER_ID}/settle").status_code == 401

    def test_contribute(self, test_client):
        assert test_client.post(f"/api/v1/rooms/{ROOM_ID}/members/{MEMBER_ID}/contribute", json={"amount": 50.0}).status_code == 401


class TestMembersAuthenticated:
    def test_list_members(self, test_client):
        r = test_client.get(f"/api/v1/rooms/{ROOM_ID}/members", headers=_auth_headers())
        assert r.status_code != 401

    def test_get_member_detail(self, test_client):
        r = test_client.get(f"/api/v1/rooms/{ROOM_ID}/members/{MEMBER_ID}", headers=_auth_headers())
        assert r.status_code != 401

    def test_update_member_role(self, test_client):
        r = test_client.patch(f"/api/v1/rooms/{ROOM_ID}/members/{MEMBER_ID}/role", json={"role": "member"}, headers=_auth_headers())
        assert r.status_code != 401

    def test_exit_room(self, test_client):
        r = test_client.delete(f"/api/v1/rooms/{ROOM_ID}/members/me", headers=_auth_headers())
        assert r.status_code != 401

    def test_remove_member(self, test_client):
        r = test_client.delete(f"/api/v1/rooms/{ROOM_ID}/members/{MEMBER_ID}", headers=_auth_headers())
        assert r.status_code != 401

    def test_settle_member(self, test_client):
        r = test_client.post(f"/api/v1/rooms/{ROOM_ID}/members/{MEMBER_ID}/settle", headers=_auth_headers())
        assert r.status_code != 401

    def test_contribute(self, test_client):
        r = test_client.post(f"/api/v1/rooms/{ROOM_ID}/members/{MEMBER_ID}/contribute", json={"amount": 50.0}, headers=_auth_headers())
        assert r.status_code != 401
