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

    def test_settle_all_unfiltered(self, test_client, make_user, make_room, add_member, make_expense):
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
