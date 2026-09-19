from app.services.expenses import expenses_services
from tests.e2e.conftest import auth_headers

ROOM_ID = 999999
EXPENSE_ID = 999999

EXPENSE_BODY = {"material": "test item", "money": 10.0}
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
        body = {**EXPENSE_BODY, "user_id": 1}
        assert test_client.post(f"/api/v1/rooms/{ROOM_ID}/expenses/for-member", json=body).status_code == 401


class TestExpensesAuthenticated:
    def test_add_expense(self, test_client, make_user, make_room):
        admin = make_user("admin@example.com", profile="https://example.com/a.png")
        room = make_room(admin)

        r = test_client.post(f"/api/v1/rooms/{room['id']}/expenses", json=EXPENSE_BODY, headers=auth_headers(admin))
        assert r.status_code == 201
        body = r.json()
        assert body["material"] == "test item"
        assert body["money"] == 10.0
        assert body["user"] == admin["email"]
        assert body["user_name"] == admin["name"]
        assert body["user_profile"] == admin["profile"]
        assert body["settled"] is None
        assert body["settled_at"] is None

    def test_add_expense_notifies_participants_except_adder(
        self, test_client, make_user, make_room, add_member, monkeypatch
    ):
        calls = []
        monkeypatch.setattr(expenses_services, "send_push", lambda conn, user_ids, **kw: calls.append((user_ids, kw)))
        admin = make_user("push-admin@example.com", name="Priya")
        in_split = make_user("push-in@example.com")
        not_in_split = make_user("push-out@example.com")
        room = make_room(admin)
        add_member(room["id"], in_split)
        add_member(room["id"], not_in_split)

        r = test_client.post(
            f"/api/v1/rooms/{room['id']}/expenses",
            json={"material": "Milk", "money": 120, "participant_user_ids": [admin["id"], in_split["id"]]},
            headers=auth_headers(admin),
        )

        assert r.status_code == 201
        [(user_ids, kw)] = calls
        assert user_ids == [in_split["id"]]
        assert kw["title"] == "Priya added Milk"
        assert kw["body"] == "₹120 · your share ₹60"
        assert kw["data"] == {"type": "expense_added", "room_id": str(room["id"]), "expense_id": str(r.json()["id"])}

    def test_add_expense_survives_failing_push_query(
        self, test_client, make_user, make_room, add_member, monkeypatch
    ):
        # A failed SQL statement aborts the Postgres transaction; send_push must
        # isolate it so the expense still commits.
        from sqlalchemy import text
        from app.services.notifications import push_service

        def broken_lookup(conn, user_ids):
            conn.execute(text("SELECT * FROM table_that_does_not_exist"))

        monkeypatch.setattr(push_service, "get_fcm_tokens_for_users", broken_lookup)
        admin = make_user("push-fail-admin@example.com")
        other = make_user("push-fail-other@example.com")
        room = make_room(admin)
        add_member(room["id"], other)

        r = test_client.post(f"/api/v1/rooms/{room['id']}/expenses", json=EXPENSE_BODY, headers=auth_headers(admin))
        assert r.status_code == 201

        r = test_client.get(f"/api/v1/rooms/{room['id']}/expenses", headers=auth_headers(admin))
        assert [e["material"] for e in r.json()["items"]] == ["test item"]

    def test_add_expense_rejects_non_positive_amount(self, test_client, make_user, make_room):
        admin = make_user("admin2@example.com")
        room = make_room(admin)

        r = test_client.post(
            f"/api/v1/rooms/{room['id']}/expenses",
            json={"material": "free", "money": 0},
            headers=auth_headers(admin),
        )
        assert r.status_code == 400

    def test_add_expense_for_member_requires_admin(self, test_client, make_user, make_room, add_member):
        admin = make_user("admin3@example.com")
        member = make_user("member3@example.com")
        room = make_room(admin)
        add_member(room["id"], member)

        body = {**EXPENSE_BODY, "user_id": member["id"]}
        r = test_client.post(f"/api/v1/rooms/{room['id']}/expenses/for-member", json=body, headers=auth_headers(member))
        assert r.status_code == 403

        r = test_client.post(f"/api/v1/rooms/{room['id']}/expenses/for-member", json=body, headers=auth_headers(admin))
        assert r.status_code == 201
        assert r.json()["user"] == member["email"]

    def test_add_expense_defaults_participants_to_all_room_members(
        self, test_client, make_user, make_room, add_member
    ):
        admin = make_user("admin-def@example.com")
        member = make_user("member-def@example.com")
        room = make_room(admin)
        add_member(room["id"], member)

        r = test_client.post(f"/api/v1/rooms/{room['id']}/expenses", json={"material": "shared", "money": 30.0}, headers=auth_headers(admin))
        assert r.status_code == 201
        expense_id = r.json()["id"]

        detail = test_client.get(f"/api/v1/rooms/{room['id']}/expenses/{expense_id}", headers=auth_headers(admin)).json()
        assert len(detail["participants"]) == 2
        by_id = {p["user_id"]: p for p in detail["participants"]}
        assert by_id[admin["id"]]["amount_paid"] == 30.0
        assert by_id[admin["id"]]["amount_owed"] == 15.0
        assert by_id[member["id"]]["amount_paid"] == 0.0
        assert by_id[member["id"]]["amount_owed"] == 15.0
        assert detail["payer_user_id"] == admin["id"]

    def test_add_expense_with_explicit_participants(self, test_client, make_user, make_room, add_member):
        admin = make_user("admin-exp@example.com")
        member = make_user("member-exp@example.com")
        outsider = make_user("outsider-exp@example.com")
        room = make_room(admin)
        add_member(room["id"], member)

        r = test_client.post(
            f"/api/v1/rooms/{room['id']}/expenses",
            json={"material": "just us two", "money": 20.0, "participant_user_ids": [admin["id"], member["id"]]},
            headers=auth_headers(admin),
        )
        assert r.status_code == 201

        r = test_client.post(
            f"/api/v1/rooms/{room['id']}/expenses",
            json={"material": "bad", "money": 20.0, "participant_user_ids": [outsider["id"]]},
            headers=auth_headers(admin),
        )
        assert r.status_code == 400

    def test_get_expense_detail_not_found(self, test_client, make_user, make_room):
        admin = make_user("admin-nf@example.com")
        room = make_room(admin)

        r = test_client.get(f"/api/v1/rooms/{room['id']}/expenses/999999", headers=auth_headers(admin))
        assert r.status_code == 404

    def test_list_expenses_pagination_and_filters(self, test_client, make_user, make_room, make_expense):
        admin = make_user("admin4@example.com")
        room = make_room(admin)
        for i in range(3):
            make_expense(room["id"], admin["email"], money=5.0 + i, material=f"item-{i}")

        r = test_client.get(f"/api/v1/rooms/{room['id']}/expenses?limit=2", headers=auth_headers(admin))
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) == 2
        assert body["next_cursor"] == body["items"][-1]["id"]

        r = test_client.get(
            f"/api/v1/rooms/{room['id']}/expenses?search=item-1", headers=auth_headers(admin)
        )
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["material"] == "item-1"

    def test_edit_expense(self, test_client, make_user, make_room, make_expense):
        admin = make_user("admin5@example.com")
        room = make_room(admin)
        expense = make_expense(room["id"], admin["email"], money=10.0, material="old")

        r = test_client.patch(
            f"/api/v1/rooms/{room['id']}/expenses/{expense['id']}",
            json={"material": "new"},
            headers=auth_headers(admin),
        )
        assert r.status_code == 200
        assert r.json()["material"] == "new"

    def test_edit_expense_nothing_to_update(self, test_client, make_user, make_room, make_expense):
        admin = make_user("admin6@example.com")
        room = make_room(admin)
        expense = make_expense(room["id"], admin["email"])

        r = test_client.patch(
            f"/api/v1/rooms/{room['id']}/expenses/{expense['id']}", json={}, headers=auth_headers(admin)
        )
        assert r.status_code == 400

    def test_edit_expense_wrong_room_is_404(self, test_client, make_user, make_room, add_member, make_expense):
        admin = make_user("admin7@example.com")
        other_admin = make_user("admin7b@example.com")
        room_a = make_room(admin)
        room_b = make_room(other_admin)
        add_member(room_b["id"], admin, role="Admin")  # admin of room_b too, so require_room_admin passes
        expense = make_expense(room_a["id"], admin["email"])

        r = test_client.patch(
            f"/api/v1/rooms/{room_b['id']}/expenses/{expense['id']}",
            json={"material": "x"},
            headers=auth_headers(admin),
        )
        assert r.status_code == 404

    def test_delete_expense(self, test_client, make_user, make_room, make_expense):
        admin = make_user("admin8@example.com")
        room = make_room(admin)
        expense = make_expense(room["id"], admin["email"])

        r = test_client.delete(f"/api/v1/rooms/{room['id']}/expenses/{expense['id']}", headers=auth_headers(admin))
        assert r.status_code == 204

        r = test_client.delete(f"/api/v1/rooms/{room['id']}/expenses/{expense['id']}", headers=auth_headers(admin))
        assert r.status_code == 404

    def test_settled_at_populated_after_settle_all(self, test_client, make_user, make_room, make_expense):
        admin = make_user("admin9@example.com")
        room = make_room(admin)
        expense = make_expense(room["id"], admin["email"], money=20.0)

        r = test_client.post(
            f"/api/v1/rooms/{room['id']}/splits/settle-all",
            json={"members": []},
            headers=auth_headers(admin),
        )
        assert r.status_code == 204

        items = test_client.get(f"/api/v1/rooms/{room['id']}/expenses", headers=auth_headers(admin)).json()["items"]
        settled = next(i for i in items if i["id"] == expense["id"])
        assert settled["settled"] is True
        assert settled["settled_at"] is not None
