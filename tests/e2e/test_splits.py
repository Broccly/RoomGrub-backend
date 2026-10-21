import json

from app.models.members.members_model import remove_user_room
from tests.e2e.conftest import auth_headers

ROOM_ID = 999999


class TestSplitsUnauthenticated:
    def test_get_splits(self, test_client):
        assert test_client.get(f"/api/v1/rooms/{ROOM_ID}/splits").status_code == 401

    def test_settle_all(self, test_client):
        body = {"members": [{"user_email": "x@example.com", "pending_amount": 100.0}]}
        assert test_client.post(f"/api/v1/rooms/{ROOM_ID}/splits/settle-all", json=body).status_code == 401


class TestSplitsAuthenticated:
    def test_get_splits(self, test_client, make_user, make_room, add_member, make_expense):
        admin = make_user("admin@example.com")
        member = make_user("member@example.com", profile="https://example.com/m.png")
        room = make_room(admin)
        add_member(room["id"], member)
        make_expense(room["id"], admin["email"], money=100.0)

        r = test_client.get(f"/api/v1/rooms/{room['id']}/splits", headers=auth_headers(admin))
        assert r.status_code == 200
        body = r.json()
        by_email = {m["user_email"]: m for m in body["members"]}
        # admin paid 100, fair share is 50 each -> admin +50, member -50
        assert by_email[admin["email"]]["pending_amount"] == 50.0
        assert by_email[member["email"]]["pending_amount"] == -50.0
        assert by_email[member["email"]]["profile"] == member["profile"]
        assert len(body["unsettled_expenses"]) == 1
        assert body["total_pending"] == 100.0

    def test_get_splits_settlements_minimal_transactions(
        self, test_client, make_user, make_room, add_member, make_expense
    ):
        a = make_user("split-a@example.com")
        b = make_user("split-b@example.com")
        c = make_user("split-c@example.com")
        room = make_room(a)
        add_member(room["id"], b)
        add_member(room["id"], c)
        make_expense(room["id"], a["email"], money=30.0)
        make_expense(room["id"], b["email"], money=60.0)

        r = test_client.get(f"/api/v1/rooms/{room['id']}/splits", headers=auth_headers(a))
        assert r.status_code == 200
        body = r.json()

        by_email = {m["user_email"]: m["pending_amount"] for m in body["members"]}
        assert by_email[a["email"]] == 0.0
        assert by_email[b["email"]] == 30.0
        assert by_email[c["email"]] == -30.0

        settlements = body["settlements"]
        assert len(settlements) == 1
        assert settlements[0]["from_user_email"] == c["email"]
        assert settlements[0]["to_user_email"] == b["email"]
        assert settlements[0]["amount"] == 30.0
        assert body["total_pending"] == 90.0

    def test_settle_all_unfiltered(
        self, test_client, make_user, make_room, add_member, make_expense, fake_redis
    ):
        admin = make_user("admin4@example.com")
        member = make_user("member4@example.com")
        room = make_room(admin)
        add_member(room["id"], member)
        make_expense(room["id"], admin["email"], money=100.0)

        splits = test_client.get(f"/api/v1/rooms/{room['id']}/splits", headers=auth_headers(admin)).json()

        r = test_client.post(
            f"/api/v1/rooms/{room['id']}/splits/settle-all",
            json={"members": splits["members"]},
            headers=auth_headers(admin),
        )
        assert r.status_code == 204

        splits_after = test_client.get(f"/api/v1/rooms/{room['id']}/splits", headers=auth_headers(admin)).json()
        assert splits_after["unsettled_expenses"] == []

        events = fake_redis.streams.get("rg:emails", [])
        assert len(events) == 1
        assert events[0]["type"] == "expense_split"
        payload = json.loads(events[0]["payload"])
        assert payload["expense_title"] == "All expenses settled up"
        assert payload["total_pending"] == 100.0

    def test_settle_all_sets_settled_at(
        self, test_client, make_user, make_room, add_member, make_expense
    ):
        admin = make_user("admin5@example.com")
        room = make_room(admin)
        expense = make_expense(room["id"], admin["email"], money=60.0)

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

    def test_settle_all_publishes_expense_split_payload(
        self, test_client, make_user, make_room, add_member, make_expense, fake_redis
    ):
        a = make_user("payload-a@example.com", name="Alice")
        b = make_user("payload-b@example.com", name="Bob")
        c = make_user("payload-c@example.com", name="Carol")
        room = make_room(a)
        add_member(room["id"], b)
        add_member(room["id"], c)
        make_expense(room["id"], a["email"], money=30.0)
        make_expense(room["id"], b["email"], money=60.0)

        splits = test_client.get(f"/api/v1/rooms/{room['id']}/splits", headers=auth_headers(a)).json()

        r = test_client.post(
            f"/api/v1/rooms/{room['id']}/splits/settle-all",
            json={"members": splits["members"]},
            headers=auth_headers(a),
        )
        assert r.status_code == 204

        events = fake_redis.streams.get("rg:emails", [])
        assert len(events) == 1
        assert events[0]["type"] == "expense_split"
        payload = json.loads(events[0]["payload"])

        assert payload["total_pending"] == 90.0

        members_by_email = {m["email"]: m for m in payload["members"]}
        assert members_by_email[a["email"]] == {"name": "Alice", "email": a["email"], "pending_amount": 0.0}
        assert members_by_email[b["email"]] == {"name": "Bob", "email": b["email"], "pending_amount": 30.0}
        assert members_by_email[c["email"]] == {"name": "Carol", "email": c["email"], "pending_amount": -30.0}

        assert payload["settlements"] == [
            {"from_name": "Carol", "to_name": "Bob", "amount": 30.0}
        ]


class TestSplitsHomeFields:
    @staticmethod
    def _add(test_client, room, payer, money, participants):
        r = test_client.post(
            f"/api/v1/rooms/{room['id']}/expenses",
            json={"material": "item", "money": money, "participant_user_ids": [p["id"] for p in participants]},
            headers=auth_headers(payer),
        )
        assert r.status_code == 201

    @staticmethod
    def _settle(test_client, room, admin):
        r = test_client.post(
            f"/api/v1/rooms/{room['id']}/splits/settle-all", json={"members": []}, headers=auth_headers(admin)
        )
        assert r.status_code == 204

    def test_per_member_and_room_totals(self, test_client, make_user, make_room, add_member):
        a = make_user("home-a@example.com", name="A")
        b = make_user("home-b@example.com", name="B")
        c = make_user("home-c@example.com", name="C")
        room = make_room(a)
        add_member(room["id"], b)
        add_member(room["id"], c)

        self._add(test_client, room, a, 90, [a, b, c])  # settled below
        self._add(test_client, room, b, 30, [b, c])  # settled below
        self._settle(test_client, room, a)
        self._add(test_client, room, a, 60, [a, b])  # the only unsettled one

        r = test_client.get(f"/api/v1/rooms/{room['id']}/splits", headers=auth_headers(b))
        assert r.status_code == 200
        body = r.json()

        members = {m["user_id"]: m for m in body["members"]}
        assert members[a["id"]] == {
            "user_id": a["id"], "user_email": a["email"], "name": "A", "profile": None, "role": "Admin",
            "pending_amount": 30.0, "unsettled_spent": 60.0, "unsettled_share": 30.0, "total_spent": 150.0,
        }
        assert members[b["id"]] == {
            "user_id": b["id"], "user_email": b["email"], "name": "B", "profile": None, "role": "Member",
            "pending_amount": -30.0, "unsettled_spent": 0.0, "unsettled_share": 30.0, "total_spent": 30.0,
        }
        assert members[c["id"]] == {
            "user_id": c["id"], "user_email": c["email"], "name": "C", "profile": None, "role": "Member",
            "pending_amount": 0.0, "unsettled_spent": 0.0, "unsettled_share": 0.0, "total_spent": 0.0,
        }
        assert [m["user_id"] for m in body["members"]] == [a["id"], c["id"], b["id"]]  # pending_amount DESC

        assert body["unsettled_count"] == 1
        assert body["total_pending"] == 60.0
        assert body["total_spent"] == 180.0
        assert body["last_settled_at"] is not None
        assert body["settlements"] == [{
            "from_user_id": b["id"], "from_user_email": b["email"], "from_name": "B",
            "to_user_id": a["id"], "to_user_email": a["email"], "to_name": "A",
            "amount": 30.0,
        }]

    def test_new_room_lists_every_member_with_zeros(self, test_client, make_user, make_room, add_member):
        admin = make_user("fresh-admin@example.com")
        member = make_user("fresh-member@example.com")
        room = make_room(admin)
        add_member(room["id"], member)

        body = test_client.get(f"/api/v1/rooms/{room['id']}/splits", headers=auth_headers(admin)).json()

        assert {m["user_id"] for m in body["members"]} == {admin["id"], member["id"]}
        for m in body["members"]:
            assert (m["pending_amount"], m["unsettled_spent"], m["unsettled_share"], m["total_spent"]) == (0, 0, 0, 0)
        assert body["unsettled_count"] == 0
        assert body["total_pending"] == 0
        assert body["total_spent"] == 0
        assert body["last_settled_at"] is None
        assert body["settlements"] == []

    def test_include_expenses_false_skips_only_the_list(self, test_client, make_user, make_room, add_member):
        admin = make_user("lite-admin@example.com")
        member = make_user("lite-member@example.com")
        room = make_room(admin)
        add_member(room["id"], member)
        self._add(test_client, room, admin, 50, [admin, member])

        url = f"/api/v1/rooms/{room['id']}/splits"
        full = test_client.get(url, headers=auth_headers(admin)).json()
        lite = test_client.get(f"{url}?include_expenses=false", headers=auth_headers(admin)).json()

        assert len(full["unsettled_expenses"]) == 1
        assert lite["unsettled_expenses"] == []
        assert {k: v for k, v in lite.items() if k != "unsettled_expenses"} == {
            k: v for k, v in full.items() if k != "unsettled_expenses"
        }

    def test_member_who_left_is_listed_only_while_they_have_a_balance(
        self, test_client, conn, make_user, make_room, add_member
    ):
        admin = make_user("left-admin@example.com")
        owes = make_user("left-owes@example.com")
        clear = make_user("left-clear@example.com")
        room = make_room(admin)
        add_member(room["id"], owes)
        add_member(room["id"], clear)
        self._settle(test_client, room, admin)  # gives everyone a 0 active balance row
        self._add(test_client, room, admin, 60, [admin, owes])

        remove_user_room(conn, room["id"], owes["id"])
        remove_user_room(conn, room["id"], clear["id"])

        body = test_client.get(f"/api/v1/rooms/{room['id']}/splits", headers=auth_headers(admin)).json()
        members = {m["user_id"]: m for m in body["members"]}

        assert set(members) == {admin["id"], owes["id"]}
        assert members[owes["id"]]["role"] is None
        assert members[owes["id"]]["pending_amount"] == -30.0
