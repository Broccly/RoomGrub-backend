from sqlalchemy import text
from app.models.expenses.expenses_model import insert_expense
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
        assert body["user"] == admin["name"]
        assert body["user_name"] == admin["name"]
        assert body["user_profile"] == admin["profile"]
        assert body["settled"] is None
        assert body["settled_at"] is None

    def test_list_expenses_shows_the_name_of_a_member_who_left(
        self, test_client, make_user, make_room, add_member, make_expense, conn
    ):
        admin = make_user("admin-left@example.com", name="Asha")
        member = make_user("member-left@example.com", name="Maya")
        room = make_room(admin)
        add_member(room["id"], member)
        make_expense(room["id"], member["email"], money=12.0)
        # Older data can hold an expense paid by someone who has since left the room.
        conn.execute(
            text('DELETE FROM "UserRooms" WHERE room_id = :room_id AND user_id = :uid'),
            {"room_id": room["id"], "uid": member["id"]},
        )

        r = test_client.get(f"/api/v1/rooms/{room['id']}/expenses", headers=auth_headers(admin))
        assert r.status_code == 200
        # The payer is shown by name, never by the email stored on the expense.
        assert [(e["user"], e["user_name"]) for e in r.json()["items"]] == [("Maya", "Maya")]

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
        assert r.json()["user"] == member["name"]

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

    def test_settled_expense_cannot_be_edited_or_deleted(self, test_client, make_user, make_room, add_member):
        admin = make_user("settled-admin@example.com")
        member = make_user("settled-member@example.com")
        room = make_room(admin)
        add_member(room["id"], member)
        headers = auth_headers(admin)

        expense = test_client.post(
            f"/api/v1/rooms/{room['id']}/expenses", json={"material": "Rent", "money": 100}, headers=headers
        ).json()
        r = test_client.post(
            f"/api/v1/rooms/{room['id']}/splits/settle-all", json={"members": []}, headers=headers
        )
        assert r.status_code == 204

        url = f"/api/v1/rooms/{room['id']}/expenses/{expense['id']}"
        r = test_client.patch(url, json={"money": 40}, headers=headers)
        assert r.status_code == 409
        r = test_client.delete(url, headers=headers)
        assert r.status_code == 409

        # The settled expense is intact and the fresh balances were not touched.
        assert test_client.get(url, headers=headers).json()["money"] == 100
        splits = test_client.get(f"/api/v1/rooms/{room['id']}/splits", headers=headers).json()
        assert all(m["pending_amount"] == 0 for m in splits["members"])


class TestEditExpenseParticipants:
    @staticmethod
    def _setup(test_client, make_user, make_room, add_member, tag: str):
        admin = make_user(f"{tag}-admin@example.com")
        m1 = make_user(f"{tag}-m1@example.com")
        m2 = make_user(f"{tag}-m2@example.com")
        room = make_room(admin)
        add_member(room["id"], m1)
        add_member(room["id"], m2)
        headers = auth_headers(admin)
        expense = test_client.post(
            f"/api/v1/rooms/{room['id']}/expenses", json={"material": "Rent", "money": 90}, headers=headers
        ).json()
        url = f"/api/v1/rooms/{room['id']}/expenses/{expense['id']}"
        return admin, m1, m2, room, headers, url

    @staticmethod
    def _balances(test_client, room, headers) -> dict[str, float]:
        splits = test_client.get(f"/api/v1/rooms/{room['id']}/splits", headers=headers).json()
        return {m["user_email"]: m["pending_amount"] for m in splits["members"]}

    def test_narrow_the_split(self, test_client, make_user, make_room, add_member):
        admin, m1, m2, room, headers, url = self._setup(test_client, make_user, make_room, add_member, "narrow")

        r = test_client.patch(url, json={"participant_user_ids": [admin["id"], m1["id"]]}, headers=headers)
        assert r.status_code == 200
        assert r.json()["money"] == 90

        participants = test_client.get(url, headers=headers).json()["participants"]
        assert {p["user_id"]: p["amount_owed"] for p in participants} == {admin["id"]: 45, m1["id"]: 45}
        assert self._balances(test_client, room, headers) == {
            admin["email"]: 45, m1["email"]: -45, m2["email"]: 0,
        }

    def test_change_money_and_participants_together(self, test_client, make_user, make_room, add_member):
        admin, m1, m2, room, headers, url = self._setup(test_client, make_user, make_room, add_member, "both")

        r = test_client.patch(
            url, json={"money": 60, "participant_user_ids": [admin["id"], m2["id"]]}, headers=headers
        )
        assert r.status_code == 200
        assert self._balances(test_client, room, headers) == {
            admin["email"]: 30, m1["email"]: 0, m2["email"]: -30,
        }

    def test_payer_cannot_be_changed(self, test_client, make_user, make_room, add_member):
        admin, m1, m2, room, headers, url = self._setup(test_client, make_user, make_room, add_member, "payer")

        for body in ({"user_id": m1["id"]}, {"user_id": m1["id"], "money": 90}, {"payer_user_id": m1["id"]}):
            r = test_client.patch(url, json=body, headers=headers)
            assert r.status_code == 422

        assert test_client.get(url, headers=headers).json()["payer_user_id"] == admin["id"]
        assert self._balances(test_client, room, headers) == {
            admin["email"]: 60, m1["email"]: -30, m2["email"]: -30,
        }

    def test_invalid_participant_lists_are_rejected(self, test_client, make_user, make_room, add_member):
        admin, m1, m2, room, headers, url = self._setup(test_client, make_user, make_room, add_member, "bad")
        outsider = make_user("bad-outsider@example.com")

        for ids, detail in [
            ([], "Pick at least one participant"),
            ([admin["id"], outsider["id"]], f"Not room members: [{outsider['id']}]"),
            ([m1["id"], m2["id"]], "The payer must be part of the split"),
        ]:
            r = test_client.patch(url, json={"participant_user_ids": ids}, headers=headers)
            assert r.status_code == 400
            assert r.json()["detail"] == detail

        # Rejected edits leave the original three-way split in place.
        assert self._balances(test_client, room, headers) == {
            admin["email"]: 60, m1["email"]: -30, m2["email"]: -30,
        }

    def test_money_edit_keeps_the_existing_split(self, test_client, make_user, make_room, add_member):
        admin, m1, m2, room, headers, url = self._setup(test_client, make_user, make_room, add_member, "keep")
        test_client.patch(url, json={"participant_user_ids": [admin["id"], m1["id"]]}, headers=headers)

        r = test_client.patch(url, json={"money": 60}, headers=headers)
        assert r.status_code == 200

        participants = test_client.get(url, headers=headers).json()["participants"]
        assert {p["user_id"]: p["amount_owed"] for p in participants} == {admin["id"]: 30, m1["id"]: 30}
        assert self._balances(test_client, room, headers) == {
            admin["email"]: 30, m1["email"]: -30, m2["email"]: 0,
        }

    def test_money_edit_rejected_when_payer_is_outside_the_split(
        self, test_client, make_user, make_room, add_member, conn
    ):
        admin, m1, m2, room, headers, url = self._setup(test_client, make_user, make_room, add_member, "outside")
        # Expenses created before the payer was required in the split have no payer row.
        expense_id = int(url.rsplit("/", 1)[1])
        conn.execute(
            text('DELETE FROM "SpendingSplits" WHERE spending_id = :id AND user_id = :uid'),
            {"id": expense_id, "uid": admin["id"]},
        )

        r = test_client.patch(url, json={"money": 60}, headers=headers)
        assert r.status_code == 400
        assert "participant_user_ids" in r.json()["detail"]

        participants = test_client.get(url, headers=headers).json()["participants"]
        assert {p["user_id"]: p["amount_owed"] for p in participants} == {m1["id"]: 30, m2["id"]: 30}

    def test_edit_and_delete_rejected_when_payer_left(
        self, test_client, make_user, make_room, add_member, make_expense, conn
    ):
        admin, m1, m2, room, headers, _ = self._setup(test_client, make_user, make_room, add_member, "left")
        expense = make_expense(room["id"], m1["email"], money=30.0)
        url = f"/api/v1/rooms/{room['id']}/expenses/{expense['id']}"
        # The API no longer lets a member with unsettled expenses leave; simulate older data.
        conn.execute(
            text('DELETE FROM "UserRooms" WHERE room_id = :room_id AND user_id = :uid'),
            {"room_id": room["id"], "uid": m1["id"]},
        )
        before = self._balances(test_client, room, headers)

        for r in (
            test_client.patch(url, json={"money": 60}, headers=headers),
            test_client.patch(url, json={"participant_user_ids": [admin["id"], m2["id"]]}, headers=headers),
            test_client.delete(url, headers=headers),
        ):
            assert r.status_code == 400
            assert r.json()["detail"] == "The person who paid for this expense has left the room, so it can't be changed"

        assert self._balances(test_client, room, headers) == before


class TestAddExpensePayerInSplit:
    def test_add_expense_requires_payer_in_participants(self, test_client, make_user, make_room, add_member):
        admin = make_user("payer-add-admin@example.com")
        m1 = make_user("payer-add-m1@example.com")
        room = make_room(admin)
        add_member(room["id"], m1)

        r = test_client.post(
            f"/api/v1/rooms/{room['id']}/expenses",
            json={"material": "Gift", "money": 40, "participant_user_ids": [m1["id"]]},
            headers=auth_headers(admin),
        )
        assert r.status_code == 400
        assert r.json()["detail"] == "The payer must be part of the split"

    def test_add_for_member_requires_payer_in_participants(self, test_client, make_user, make_room, add_member):
        admin = make_user("payer-for-admin@example.com")
        m1 = make_user("payer-for-m1@example.com")
        room = make_room(admin)
        add_member(room["id"], m1)

        r = test_client.post(
            f"/api/v1/rooms/{room['id']}/expenses/for-member",
            json={"material": "Gift", "money": 40, "user_id": m1["id"], "participant_user_ids": [admin["id"]]},
            headers=auth_headers(admin),
        )
        assert r.status_code == 400
        assert r.json()["detail"] == "The payer must be part of the split"


class TestExpenseOwnerPermissions:
    @staticmethod
    def _setup(test_client, make_user, make_room, add_member, tag: str):
        admin = make_user(f"{tag}-admin@example.com")
        owner = make_user(f"{tag}-owner@example.com")
        other = make_user(f"{tag}-other@example.com")
        room = make_room(admin)
        add_member(room["id"], owner)
        add_member(room["id"], other)
        expense = test_client.post(
            f"/api/v1/rooms/{room['id']}/expenses",
            json={"material": "Milk", "money": 90},
            headers=auth_headers(owner),
        ).json()
        url = f"/api/v1/rooms/{room['id']}/expenses/{expense['id']}"
        return admin, owner, other, room, url

    @staticmethod
    def _balances(test_client, room, user) -> dict[str, float]:
        splits = test_client.get(f"/api/v1/rooms/{room['id']}/splits", headers=auth_headers(user)).json()
        return {m["user_email"]: m["pending_amount"] for m in splits["members"]}

    def test_owner_can_edit_including_participants(self, test_client, make_user, make_room, add_member):
        admin, owner, other, room, url = self._setup(test_client, make_user, make_room, add_member, "own-edit")

        r = test_client.patch(
            url,
            json={"material": "Milk + bread", "participant_user_ids": [owner["id"], other["id"]]},
            headers=auth_headers(owner),
        )
        assert r.status_code == 200
        assert r.json()["material"] == "Milk + bread"
        assert self._balances(test_client, room, owner) == {
            admin["email"]: 0, owner["email"]: 45, other["email"]: -45,
        }

    def test_owner_can_delete(self, test_client, make_user, make_room, add_member):
        admin, owner, other, room, url = self._setup(test_client, make_user, make_room, add_member, "own-del")

        r = test_client.delete(url, headers=auth_headers(owner))
        assert r.status_code == 204
        assert test_client.get(url, headers=auth_headers(owner)).status_code == 404
        assert all(v == 0 for v in self._balances(test_client, room, owner).values())

    def test_other_member_cannot_edit_or_delete(self, test_client, make_user, make_room, add_member):
        admin, owner, other, room, url = self._setup(test_client, make_user, make_room, add_member, "not-own")

        r = test_client.patch(url, json={"material": "x"}, headers=auth_headers(other))
        assert r.status_code == 403
        r = test_client.delete(url, headers=auth_headers(other))
        assert r.status_code == 403
        assert test_client.get(url, headers=auth_headers(other)).json()["material"] == "Milk"

    def test_admin_can_still_edit_and_delete_any_expense(self, test_client, make_user, make_room, add_member):
        admin, owner, other, room, url = self._setup(test_client, make_user, make_room, add_member, "admin-any")

        assert test_client.patch(url, json={"money": 30}, headers=auth_headers(admin)).status_code == 200
        assert test_client.delete(url, headers=auth_headers(admin)).status_code == 204

    def test_member_owns_expense_an_admin_added_for_them(self, test_client, make_user, make_room, add_member):
        admin = make_user("for-admin@example.com")
        member = make_user("for-member@example.com")
        room = make_room(admin)
        add_member(room["id"], member)
        expense = test_client.post(
            f"/api/v1/rooms/{room['id']}/expenses/for-member",
            json={"material": "Gas", "money": 50, "user_id": member["id"]},
            headers=auth_headers(admin),
        ).json()

        r = test_client.delete(
            f"/api/v1/rooms/{room['id']}/expenses/{expense['id']}", headers=auth_headers(member)
        )
        assert r.status_code == 204

    def test_owner_cannot_change_settled_expense(self, test_client, make_user, make_room, add_member):
        admin, owner, other, room, url = self._setup(test_client, make_user, make_room, add_member, "own-settled")
        test_client.post(
            f"/api/v1/rooms/{room['id']}/splits/settle-all", json={"members": []}, headers=auth_headers(admin)
        )

        assert test_client.patch(url, json={"material": "x"}, headers=auth_headers(owner)).status_code == 409
        assert test_client.delete(url, headers=auth_headers(owner)).status_code == 409


class TestFrequentItems:
    @staticmethod
    def _room_with(conn, make_user, make_room, tag: str, materials: list[str]):
        """A room whose expenses are `materials`, oldest first."""
        admin = make_user(f"{tag}@example.com")
        room = make_room(admin)
        for material in materials:
            insert_expense(conn, room["id"], admin["id"], admin["email"], material, 10)
        return admin, room

    @staticmethod
    def _get(test_client, room, user, query: str = ""):
        return test_client.get(f"/api/v1/rooms/{room['id']}/expenses/frequent-items{query}", headers=auth_headers(user))

    def test_ranking(self, test_client, conn, make_user, make_room):
        admin, room = self._room_with(conn, make_user, make_room, "freq-rank", [
            "Milk",
            "bread, Eggs",
            "milk",
            "Eggs",
            "  ,Rice , ",
            "Bread",
        ])

        r = self._get(test_client, room, admin)
        assert r.status_code == 200
        # Bread, Eggs and milk are used twice each, so the most recent wins the tie;
        # each name keeps its latest spelling, and blanks are dropped.
        assert r.json() == {"items": ["Bread", "Eggs", "milk", "Rice"]}

    def test_only_the_latest_100_expenses_count(self, test_client, conn, make_user, make_room):
        admin, room = self._room_with(conn, make_user, make_room, "freq-window", ["Ancient"] + ["Fresh"] * 100)

        assert self._get(test_client, room, admin).json() == {"items": ["Fresh"]}

    def test_limit(self, test_client, conn, make_user, make_room):
        # Seven distinct items, one more than the default, so the default has to cut the list.
        # Milk ×3, Bread ×2, Eggs ×2, then Rice, Oil, Sugar, Tea once each.
        admin, room = self._room_with(conn, make_user, make_room, "freq-limit", [
            "Milk", "Bread", "Milk", "Eggs", "Rice", "Milk", "Bread", "Oil", "Sugar", "Tea", "Eggs",
        ])

        # Most used first; Eggs beats Bread on the tie because it was used more recently.
        assert self._get(test_client, room, admin, "?limit=2").json() == {"items": ["Milk", "Eggs"]}
        # Default 6 drops Rice: used once, and the oldest of the single-use items.
        assert self._get(test_client, room, admin).json() == {
            "items": ["Milk", "Eggs", "Bread", "Tea", "Sugar", "Oil"],
        }
        assert self._get(test_client, room, admin, "?limit=21").status_code == 422
        assert self._get(test_client, room, admin, "?limit=0").status_code == 422

    def test_empty_room(self, test_client, make_user, make_room):
        admin = make_user("freq-empty@example.com")
        room = make_room(admin)

        assert self._get(test_client, room, admin).json() == {"items": []}

    def test_does_not_shadow_expense_detail(self, test_client, conn, make_user, make_room):
        admin, room = self._room_with(conn, make_user, make_room, "freq-route", ["Milk"])
        expense_id = test_client.get(
            f"/api/v1/rooms/{room['id']}/expenses", headers=auth_headers(admin)
        ).json()["items"][0]["id"]

        r = test_client.get(f"/api/v1/rooms/{room['id']}/expenses/{expense_id}", headers=auth_headers(admin))
        assert r.status_code == 200
        assert r.json()["material"] == "Milk"

    def test_requires_membership(self, test_client, conn, make_user, make_room):
        admin, room = self._room_with(conn, make_user, make_room, "freq-member", ["Milk"])
        outsider = make_user("freq-outsider@example.com")

        assert self._get(test_client, room, outsider).status_code == 403
