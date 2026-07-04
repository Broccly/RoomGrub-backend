from tests.e2e.conftest import _auth_headers

ROOM_ID = 999999


class TestRoomsUnauthenticated:
    def test_list_rooms(self, test_client):
        assert test_client.get("/api/v1/rooms").status_code == 401

    def test_create_room(self, test_client):
        assert test_client.post("/api/v1/rooms", json={}).status_code == 401

    def test_get_room(self, test_client):
        assert test_client.get(f"/api/v1/rooms/{ROOM_ID}").status_code == 401

    def test_get_room_dashboard(self, test_client):
        assert test_client.get(f"/api/v1/rooms/{ROOM_ID}/dashboard").status_code == 401

    def test_delete_room(self, test_client):
        assert test_client.delete(f"/api/v1/rooms/{ROOM_ID}").status_code == 401


class TestRoomsAuthenticated:
    def test_list_rooms(self, test_client):
        r = test_client.get("/api/v1/rooms", headers=_auth_headers())
        assert r.status_code == 200

    def test_create_room(self, test_client):
        r = test_client.post("/api/v1/rooms", json={}, headers=_auth_headers())
        assert r.status_code != 401

    def test_get_room(self, test_client):
        r = test_client.get(f"/api/v1/rooms/{ROOM_ID}", headers=_auth_headers())
        assert r.status_code != 401

    def test_get_room_dashboard(self, test_client):
        r = test_client.get(f"/api/v1/rooms/{ROOM_ID}/dashboard", headers=_auth_headers())
        assert r.status_code != 401

    def test_delete_room(self, test_client):
        r = test_client.delete(f"/api/v1/rooms/{ROOM_ID}", headers=_auth_headers())
        assert r.status_code != 401
