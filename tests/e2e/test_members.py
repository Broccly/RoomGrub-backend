from tests.e2e.conftest import auth_headers

ROOM_ID = 999999
MEMBER_ID = 999999


class TestMembersUnauthenticated:
    def test_list_members(self, test_client):
        assert test_client.get(f"/api/v1/rooms/{ROOM_ID}/members").status_code == 401

    def test_get_member_detail(self, test_client):
        assert test_client.get(f"/api/v1/rooms/{ROOM_ID}/members/{MEMBER_ID}").status_code == 401

    def test_update_member_role(self, test_client):
        assert test_client.patch(f"/api/v1/rooms/{ROOM_ID}/members/{MEMBER_ID}/role", json={"role": "Member"}).status_code == 401

    def test_exit_room(self, test_client):
        assert test_client.delete(f"/api/v1/rooms/{ROOM_ID}/members/me").status_code == 401

    def test_remove_member(self, test_client):
        assert test_client.delete(f"/api/v1/rooms/{ROOM_ID}/members/{MEMBER_ID}").status_code == 401


class TestMembersAuthenticated:
    def test_list_members(self, test_client, make_user, make_room, add_member):
        admin = make_user("admin@example.com")
        member = make_user("member@example.com", profile="https://example.com/m.png")
        room = make_room(admin)
        add_member(room["id"], member)

        r = test_client.get(f"/api/v1/rooms/{room['id']}/members", headers=auth_headers(admin))
        assert r.status_code == 200
        by_email = {m["email"]: m for m in r.json()}
        assert by_email[admin["email"]]["role"] == "Admin"
        assert by_email[member["email"]]["role"] == "Member"
        assert by_email[member["email"]]["profile"] == member["profile"]

    def test_get_member_detail(self, test_client, make_user, make_room, add_member, make_expense):
        admin = make_user("admin2@example.com")
        member = make_user("member2@example.com")
        room = make_room(admin)
        add_member(room["id"], member)
        make_expense(room["id"], member["email"], money=30.0)

        r = test_client.get(
            f"/api/v1/rooms/{room['id']}/members/{member['id']}", headers=auth_headers(admin)
        )
        assert r.status_code == 200
        body = r.json()
        assert body["total_spent"] == 30.0
        assert body["pending_amount"] == 30.0
        assert len(body["expenses"]) == 1

    def test_get_member_detail_not_found(self, test_client, make_user, make_room):
        admin = make_user("admin3@example.com")
        room = make_room(admin)

        r = test_client.get(f"/api/v1/rooms/{room['id']}/members/{MEMBER_ID}", headers=auth_headers(admin))
        assert r.status_code == 404

    def test_update_member_role(self, test_client, make_user, make_room, add_member):
        admin = make_user("admin4@example.com")
        member = make_user("member4@example.com")
        room = make_room(admin)
        add_member(room["id"], member)

        r = test_client.patch(
            f"/api/v1/rooms/{room['id']}/members/{member['id']}/role",
            json={"role": "Admin"},
            headers=auth_headers(admin),
        )
        assert r.status_code == 204

        members = test_client.get(f"/api/v1/rooms/{room['id']}/members", headers=auth_headers(admin)).json()
        assert next(m for m in members if m["email"] == member["email"])["role"] == "Admin"

    def test_update_member_role_invalid_value(self, test_client, make_user, make_room, add_member):
        admin = make_user("admin5@example.com")
        member = make_user("member5@example.com")
        room = make_room(admin)
        add_member(room["id"], member)

        r = test_client.patch(
            f"/api/v1/rooms/{room['id']}/members/{member['id']}/role",
            json={"role": "Superuser"},
            headers=auth_headers(admin),
        )
        assert r.status_code == 400

    def test_admin_cannot_demote_self(self, test_client, make_user, make_room):
        admin = make_user("admin6@example.com")
        room = make_room(admin)

        r = test_client.patch(
            f"/api/v1/rooms/{room['id']}/members/{admin['id']}/role",
            json={"role": "Member"},
            headers=auth_headers(admin),
        )
        assert r.status_code == 400

    def test_exit_room(self, test_client, make_user, make_room, add_member):
        admin = make_user("admin7@example.com")
        member = make_user("member7@example.com")
        room = make_room(admin)
        add_member(room["id"], member)

        r = test_client.delete(f"/api/v1/rooms/{room['id']}/members/me", headers=auth_headers(member))
        assert r.status_code == 204

    def test_admin_cannot_exit_room(self, test_client, make_user, make_room):
        admin = make_user("admin8@example.com")
        room = make_room(admin)

        r = test_client.delete(f"/api/v1/rooms/{room['id']}/members/me", headers=auth_headers(admin))
        assert r.status_code == 403

    def test_exit_room_with_outstanding_balance(self, test_client, make_user, make_room, add_member, make_expense):
        admin = make_user("admin11@example.com")
        member = make_user("member11@example.com")
        room = make_room(admin)
        add_member(room["id"], member)
        make_expense(room["id"], admin["email"], money=30.0)

        r = test_client.delete(f"/api/v1/rooms/{room['id']}/members/me", headers=auth_headers(member))
        assert r.status_code == 400

    def test_remove_member(self, test_client, make_user, make_room, add_member):
        admin = make_user("admin9@example.com")
        member = make_user("member9@example.com")
        room = make_room(admin)
        add_member(room["id"], member)

        r = test_client.delete(f"/api/v1/rooms/{room['id']}/members/{member['id']}", headers=auth_headers(admin))
        assert r.status_code == 204

    def test_remove_member_with_outstanding_balance(self, test_client, make_user, make_room, add_member, make_expense):
        admin = make_user("admin12@example.com")
        member = make_user("member12@example.com")
        room = make_room(admin)
        add_member(room["id"], member)
        make_expense(room["id"], admin["email"], money=30.0)

        r = test_client.delete(f"/api/v1/rooms/{room['id']}/members/{member['id']}", headers=auth_headers(admin))
        assert r.status_code == 400

    def test_admin_cannot_remove_self(self, test_client, make_user, make_room):
        admin = make_user("admin10@example.com")
        room = make_room(admin)

        r = test_client.delete(f"/api/v1/rooms/{room['id']}/members/{admin['id']}", headers=auth_headers(admin))
        assert r.status_code == 400
