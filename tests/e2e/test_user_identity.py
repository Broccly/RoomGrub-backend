import uuid

from sqlalchemy import text

from app.services.auth import auth_services
from tests.e2e.conftest import auth_headers


def _make_user_without_email(conn, name: str) -> dict:
    # Stands in for the guests and placeholders of docs/GUEST_ACCESS.md, which have no email.
    row = conn.execute(
        text('INSERT INTO "Users" (name) VALUES (:name) RETURNING id, email, name, profile'),
        {"name": name},
    ).fetchone()
    return dict(row._mapping)


class TestUserWithoutEmail:
    def test_pays_splits_and_settles(self, conn, test_client, make_user, make_room, add_member):
        admin = make_user("identity-admin@example.com")
        guest = _make_user_without_email(conn, "Ravi")
        room = make_room(admin)
        add_member(room["id"], guest)
        base = f"/api/v1/rooms/{room['id']}"

        # The user without an email pays, split with everyone.
        r = test_client.post(f"{base}/expenses", json={"material": "milk", "money": 100}, headers=auth_headers(guest))
        assert r.status_code == 201
        expense = r.json()
        assert expense["user"] is None
        assert expense["user_name"] == "Ravi"
        assert conn.execute(
            text('SELECT "user" FROM "Spendings" WHERE id = :id'), {"id": expense["id"]}
        ).scalar() is None

        items = test_client.get(f"{base}/expenses", headers=auth_headers(admin)).json()["items"]
        assert [(i["id"], i["user_name"]) for i in items] == [(expense["id"], "Ravi")]

        detail = test_client.get(f"{base}/expenses/{expense['id']}", headers=auth_headers(admin)).json()
        assert detail["payer_user_id"] == guest["id"]

        member = test_client.get(f"{base}/members/{guest['id']}", headers=auth_headers(admin)).json()
        assert member["email"] is None
        assert member["pending_amount"] == 100.0
        assert [e["id"] for e in member["expenses"]] == [expense["id"]]

        dashboard = test_client.get(f"{base}/dashboard", headers=auth_headers(admin)).json()
        assert {m["user_id"]: m["pending_amount"] for m in dashboard["members"]}[guest["id"]] == 100.0

        splits = test_client.get(f"{base}/splits", headers=auth_headers(admin)).json()
        balances = {m["user_id"]: m for m in splits["members"]}
        assert balances[guest["id"]]["user_email"] is None
        assert balances[guest["id"]]["pending_amount"] == 50.0
        assert splits["unsettled_expenses"][0]["user"] is None
        assert splits["settlements"][0]["to_user_id"] == guest["id"]
        assert splits["settlements"][0]["to_user_email"] is None

        body = {"members": [{"user_id": m["user_id"], "pending_amount": m["pending_amount"]} for m in splits["members"]]}
        assert test_client.post(f"{base}/splits/settle-all", json=body, headers=auth_headers(admin)).status_code == 204

    def test_access_token_has_no_email_claim(self, conn, test_client):
        guest = _make_user_without_email(conn, "No Mail")
        r = test_client.get("/api/v1/rooms", headers=auth_headers(guest))
        assert r.status_code == 200


class TestSettleAllIdentifiers:
    def _room_with_debt(self, test_client, make_user, make_room, add_member, make_expense):
        admin = make_user("settle-id-admin@example.com")
        member = make_user("settle-id-member@example.com")
        room = make_room(admin)
        add_member(room["id"], member)
        make_expense(room["id"], admin["email"], money=100.0)
        return admin, member, room

    def test_by_user_email_still_works(self, test_client, make_user, make_room, add_member, make_expense):
        admin, member, room = self._room_with_debt(test_client, make_user, make_room, add_member, make_expense)
        body = {"members": [
            {"user_email": admin["email"], "pending_amount": 50.0},
            {"user_email": member["email"], "pending_amount": -50.0},
        ]}
        r = test_client.post(f"/api/v1/rooms/{room['id']}/splits/settle-all", json=body, headers=auth_headers(admin))
        assert r.status_code == 204

    def test_mismatch_by_user_id_names_the_user(self, test_client, make_user, make_room, add_member, make_expense):
        admin, member, room = self._room_with_debt(test_client, make_user, make_room, add_member, make_expense)
        body = {"members": [{"user_id": member["id"], "pending_amount": -10.0}]}
        r = test_client.post(f"/api/v1/rooms/{room['id']}/splits/settle-all", json=body, headers=auth_headers(admin))
        assert r.status_code == 400
        assert f"user {member['id']}" in r.json()["detail"]

    def test_member_without_identifier_is_rejected(self, test_client, make_user, make_room):
        admin = make_user("settle-id-none@example.com")
        room = make_room(admin)
        body = {"members": [{"pending_amount": 0.0}]}
        r = test_client.post(f"/api/v1/rooms/{room['id']}/splits/settle-all", json=body, headers=auth_headers(admin))
        assert r.status_code == 422


class TestExpenseFilterByUserId:
    def test_filters_by_payer(self, test_client, make_user, make_room, add_member, make_expense):
        admin = make_user("filter-admin@example.com")
        member = make_user("filter-member@example.com")
        room = make_room(admin)
        add_member(room["id"], member)
        make_expense(room["id"], admin["email"], material="admin's")
        mine = make_expense(room["id"], member["email"], material="member's")

        url = f"/api/v1/rooms/{room['id']}/expenses"
        by_id = test_client.get(url, params={"user_id": member["id"]}, headers=auth_headers(admin)).json()["items"]
        by_email = test_client.get(url, params={"user_email": member["email"]}, headers=auth_headers(admin)).json()["items"]
        assert [i["id"] for i in by_id] == [mine["id"]]
        assert [i["id"] for i in by_email] == [mine["id"]]


class TestUid:
    def test_login_generates_uid_once(self, conn, test_client, monkeypatch):
        monkeypatch.setattr(
            auth_services,
            "verify_provider_token",
            lambda provider, token: {"email": "uid-user@example.com", "name": "Uid User", "picture": None},
        )
        first = test_client.post("/api/v1/auth/login", json={"provider": "google", "token": "t"}).json()
        uid_sql = text('SELECT uid FROM "Users" WHERE id = :id')
        uid = conn.execute(uid_sql, {"id": first["user"]["id"]}).scalar()
        uuid.UUID(uid)

        test_client.post("/api/v1/auth/login", json={"provider": "facebook", "token": "t"})
        assert conn.execute(uid_sql, {"id": first["user"]["id"]}).scalar() == uid

    def test_room_gets_a_uid(self, conn, test_client, make_user):
        admin = make_user("uid-room@example.com", name="Room Admin")
        r = test_client.post("/api/v1/rooms", headers=auth_headers(admin))
        assert r.status_code == 201
        uid = conn.execute(text('SELECT uid FROM "Rooms" WHERE id = :id'), {"id": r.json()["id"]}).scalar()
        uuid.UUID(uid)


class TestRoomAdminFields:
    def test_admin_user_id_and_name(self, test_client, make_user, make_room, add_member):
        admin = make_user("fields-admin@example.com", name="Asha")
        second = make_user("fields-second@example.com", name="Bo")
        room = make_room(admin)
        add_member(room["id"], second, role="Admin")
        expected = {"admin": admin["email"], "admin_user_id": admin["id"], "admin_name": "Asha"}

        created = test_client.post("/api/v1/rooms", headers=auth_headers(admin)).json()
        assert {k: created[k] for k in expected} == expected

        summary = test_client.get(f"/api/v1/rooms/{room['id']}", headers=auth_headers(second)).json()
        assert {k: summary[k] for k in expected} == expected

        listed = next(r for r in test_client.get("/api/v1/rooms", headers=auth_headers(second)).json() if r["id"] == room["id"])
        assert {k: listed[k] for k in expected} == expected
