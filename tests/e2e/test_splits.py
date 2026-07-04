from tests.e2e.conftest import _auth_headers

ROOM_ID = 999999

SETTLE_BODY = {"user_email": "x@example.com", "pending_amount": 100.0}
SETTLE_ALL_BODY = {"members": [{"user_email": "x@example.com", "pending_amount": 100.0}]}


class TestSplitsUnauthenticated:
    def test_get_splits(self, test_client):
        assert test_client.get(f"/api/v1/rooms/{ROOM_ID}/splits").status_code == 401

    def test_settle_one(self, test_client):
        assert test_client.post(f"/api/v1/rooms/{ROOM_ID}/splits/settle", json=SETTLE_BODY).status_code == 401

    def test_settle_all(self, test_client):
        assert test_client.post(f"/api/v1/rooms/{ROOM_ID}/splits/settle-all", json=SETTLE_ALL_BODY).status_code == 401


class TestSplitsAuthenticated:
    def test_get_splits(self, test_client):
        r = test_client.get(f"/api/v1/rooms/{ROOM_ID}/splits", headers=_auth_headers())
        assert r.status_code != 401

    def test_settle_one(self, test_client):
        r = test_client.post(f"/api/v1/rooms/{ROOM_ID}/splits/settle", json=SETTLE_BODY, headers=_auth_headers())
        assert r.status_code != 401

    def test_settle_all(self, test_client):
        r = test_client.post(f"/api/v1/rooms/{ROOM_ID}/splits/settle-all", json=SETTLE_ALL_BODY, headers=_auth_headers())
        assert r.status_code != 401
