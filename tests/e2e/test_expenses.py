from tests.e2e.conftest import _auth_headers

ROOM_ID = 999999
EXPENSE_ID = 999999

EXPENSE_BODY = {"material": "test item", "money": 10.0}
EXPENSE_FOR_MEMBER_BODY = {"material": "test item", "money": 10.0, "user_email": "x@example.com"}
EXPENSE_UPDATE_BODY = {"material": "updated item"}


class TestExpensesUnauthenticated:
    def test_list_expenses(self, test_client):
        assert test_client.get(f"/api/v1/rooms/{ROOM_ID}/expenses").status_code == 401

    def test_add_expense(self, test_client):
        assert test_client.post(f"/api/v1/rooms/{ROOM_ID}/expenses", json=EXPENSE_BODY).status_code == 401

    def test_edit_expense(self, test_client):
        assert test_client.patch(f"/api/v1/rooms/{ROOM_ID}/expenses/{EXPENSE_ID}", json=EXPENSE_UPDATE_BODY).status_code == 401

    def test_delete_expense(self, test_client):
        assert test_client.delete(f"/api/v1/rooms/{ROOM_ID}/expenses/{EXPENSE_ID}").status_code == 401

    def test_add_expense_for_member(self, test_client):
        assert test_client.post(f"/api/v1/rooms/{ROOM_ID}/expenses/for-member", json=EXPENSE_FOR_MEMBER_BODY).status_code == 401


class TestExpensesAuthenticated:
    def test_list_expenses(self, test_client):
        r = test_client.get(f"/api/v1/rooms/{ROOM_ID}/expenses", headers=_auth_headers())
        assert r.status_code != 401

    def test_add_expense(self, test_client):
        r = test_client.post(f"/api/v1/rooms/{ROOM_ID}/expenses", json=EXPENSE_BODY, headers=_auth_headers())
        assert r.status_code != 401

    def test_edit_expense(self, test_client):
        r = test_client.patch(f"/api/v1/rooms/{ROOM_ID}/expenses/{EXPENSE_ID}", json=EXPENSE_UPDATE_BODY, headers=_auth_headers())
        assert r.status_code != 401

    def test_delete_expense(self, test_client):
        r = test_client.delete(f"/api/v1/rooms/{ROOM_ID}/expenses/{EXPENSE_ID}", headers=_auth_headers())
        assert r.status_code != 401

    def test_add_expense_for_member(self, test_client):
        r = test_client.post(f"/api/v1/rooms/{ROOM_ID}/expenses/for-member", json=EXPENSE_FOR_MEMBER_BODY, headers=_auth_headers())
        assert r.status_code != 401
