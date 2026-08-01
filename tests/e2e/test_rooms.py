from tests.e2e.conftest import auth_headers

ROOM_ID = 999999


class TestRoomsUnauthenticated:
    def test_list_rooms(self, test_client):
        assert test_client.get("/api/v1/rooms").status_code == 401

    def test_create_room(self, test_client):
        assert test_client.post("/api/v1/rooms").status_code == 401

    def test_get_room(self, test_client):
        assert test_client.get(f"/api/v1/rooms/{ROOM_ID}").status_code == 401

    def test_get_room_dashboard(self, test_client):
        assert test_client.get(f"/api/v1/rooms/{ROOM_ID}/dashboard").status_code == 401

    def test_delete_room(self, test_client):
        assert test_client.delete(f"/api/v1/rooms/{ROOM_ID}").status_code == 401


class TestRoomsAuthenticated:
    def test_create_room_makes_creator_admin(self, test_client, make_user):
        admin = make_user("admin@example.com")
        r = test_client.post("/api/v1/rooms", headers=auth_headers(admin))
        assert r.status_code == 201
        body = r.json()
        assert body["members"] == 1
        assert body["admin"] == admin["email"]

        members = test_client.get(f"/api/v1/rooms/{body['id']}/members", headers=auth_headers(admin)).json()
        assert len(members) == 1
        assert members[0]["role"] == "Admin"
        assert members[0]["email"] == admin["email"]

    def test_list_rooms_only_returns_own_rooms(self, test_client, make_user, make_room):
        user_a = make_user("a@example.com")
        user_b = make_user("b@example.com")
        room_a = make_room(user_a)
        make_room(user_b)

        r = test_client.get("/api/v1/rooms", headers=auth_headers(user_a))
        assert r.status_code == 200
        ids = [room["id"] for room in r.json()]
        assert ids == [room_a["id"]]

    def test_get_room_summary(self, test_client, make_user, make_room, make_expense):
        admin = make_user("admin2@example.com")
        room = make_room(admin)
        make_expense(room["id"], admin["email"], money=25.0, material="Groceries")

        r = test_client.get(f"/api/v1/rooms/{room['id']}", headers=auth_headers(admin))
        assert r.status_code == 200
        body = r.json()
        assert body["total_spent"] == 25.0
        assert body["pending_amount"] == 25.0
        assert "recent_expenses" not in body

    def test_get_room_summary_not_found(self, test_client, make_user):
        user = make_user("nf@example.com")
        r = test_client.get(f"/api/v1/rooms/{ROOM_ID}", headers=auth_headers(user))
        assert r.status_code == 403  # not a member of a nonexistent room

    def test_get_room_dashboard(self, test_client, make_user, make_room, add_member, make_expense):
        admin = make_user("admin3@example.com")
        member = make_user("member3@example.com", profile="https://example.com/avatar.png")
        room = make_room(admin)
        add_member(room["id"], member)
        make_expense(room["id"], member["email"], money=40.0)

        r = test_client.get(f"/api/v1/rooms/{room['id']}/dashboard", headers=auth_headers(admin))
        assert r.status_code == 200
        body = r.json()
        stats = {m["user_id"]: m for m in body["members"]}
        assert stats[member["id"]]["pending_amount"] == 40.0
        assert stats[member["id"]]["profile"] == "https://example.com/avatar.png"
        assert "email" not in stats[member["id"]]
        assert "role" not in stats[member["id"]]
        assert "total_spent" not in stats[member["id"]]

    def test_delete_room(self, test_client, make_user, make_room):
        admin = make_user("admin4@example.com")
        room = make_room(admin)

        r = test_client.delete(f"/api/v1/rooms/{room['id']}", headers=auth_headers(admin))
        assert r.status_code == 204

        follow_up = test_client.get(f"/api/v1/rooms/{room['id']}", headers=auth_headers(admin))
        assert follow_up.status_code == 403  # membership row is gone too

    def test_delete_room_blocked_by_unsettled_expenses(self, test_client, make_user, make_room, make_expense):
        admin = make_user("admin5@example.com")
        room = make_room(admin)
        make_expense(room["id"], admin["email"], money=15.0)

        r = test_client.delete(f"/api/v1/rooms/{room['id']}", headers=auth_headers(admin))
        assert r.status_code == 400

    def test_delete_room_requires_admin(self, test_client, make_user, make_room, add_member):
        admin = make_user("admin6@example.com")
        member = make_user("member6@example.com")
        room = make_room(admin)
        add_member(room["id"], member)

        r = test_client.delete(f"/api/v1/rooms/{room['id']}", headers=auth_headers(member))
        assert r.status_code == 403
