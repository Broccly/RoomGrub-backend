import pytest
from tests.e2e.conftest import auth_headers

pytestmark = pytest.mark.skip(reason="Notifications router not mounted in main.py yet")

ROOM_ID = 999999

NOTIFICATION_BODY = {
    "activity_type": "expense",
    "title": "Test",
    "message": "Test notification",
}
PUSH_SUBSCRIPTION_BODY = {
    "endpoint": "https://push.example.com/sub/123",
    "p256dh_key": "dummykey",
    "auth_key": "dummyauth",
}


class TestNotificationsUnauthenticated:
    def test_create_notification(self, test_client):
        assert test_client.post(f"/api/v1/rooms/{ROOM_ID}/notifications", json=NOTIFICATION_BODY).status_code == 401

    def test_list_notifications(self, test_client):
        assert test_client.get(f"/api/v1/rooms/{ROOM_ID}/notifications").status_code == 401

    def test_register_push(self, test_client):
        assert test_client.post(f"/api/v1/rooms/{ROOM_ID}/push-subscriptions", json=PUSH_SUBSCRIPTION_BODY).status_code == 401

    def test_unregister_push(self, test_client):
        assert test_client.delete(f"/api/v1/rooms/{ROOM_ID}/push-subscriptions").status_code == 401


class TestNotificationsNonMember:
    """A user who is not a member of the room must be rejected (IDOR guard)."""

    def test_create_notification(self, test_client, make_user, make_room):
        admin = make_user("notif-admin1@example.com")
        outsider = make_user("notif-outsider1@example.com")
        room = make_room(admin)

        r = test_client.post(f"/api/v1/rooms/{room['id']}/notifications", json=NOTIFICATION_BODY, headers=auth_headers(outsider))
        assert r.status_code == 403

    def test_list_notifications(self, test_client, make_user, make_room):
        admin = make_user("notif-admin2@example.com")
        outsider = make_user("notif-outsider2@example.com")
        room = make_room(admin)

        r = test_client.get(f"/api/v1/rooms/{room['id']}/notifications", headers=auth_headers(outsider))
        assert r.status_code == 403

    def test_register_push(self, test_client, make_user, make_room):
        admin = make_user("notif-admin3@example.com")
        outsider = make_user("notif-outsider3@example.com")
        room = make_room(admin)

        r = test_client.post(
            f"/api/v1/rooms/{room['id']}/push-subscriptions", json=PUSH_SUBSCRIPTION_BODY, headers=auth_headers(outsider)
        )
        assert r.status_code == 403

    def test_unregister_push(self, test_client, make_user, make_room):
        admin = make_user("notif-admin4@example.com")
        outsider = make_user("notif-outsider4@example.com")
        room = make_room(admin)

        r = test_client.delete(f"/api/v1/rooms/{room['id']}/push-subscriptions", headers=auth_headers(outsider))
        assert r.status_code == 403


class TestNotificationsMember:
    def test_create_notification(self, test_client, make_user, make_room):
        admin = make_user("notif-admin5@example.com")
        room = make_room(admin)

        r = test_client.post(f"/api/v1/rooms/{room['id']}/notifications", json=NOTIFICATION_BODY, headers=auth_headers(admin))
        assert r.status_code == 201
        body = r.json()
        assert body["room_id"] == room["id"]
        assert body["title"] == "Test"

    def test_list_notifications(self, test_client, make_user, make_room):
        admin = make_user("notif-admin6@example.com")
        room = make_room(admin)
        test_client.post(f"/api/v1/rooms/{room['id']}/notifications", json=NOTIFICATION_BODY, headers=auth_headers(admin))

        r = test_client.get(f"/api/v1/rooms/{room['id']}/notifications", headers=auth_headers(admin))
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_register_and_unregister_push(self, test_client, make_user, make_room):
        admin = make_user("notif-admin7@example.com")
        room = make_room(admin)

        r = test_client.post(
            f"/api/v1/rooms/{room['id']}/push-subscriptions", json=PUSH_SUBSCRIPTION_BODY, headers=auth_headers(admin)
        )
        assert r.status_code == 204

        r = test_client.delete(f"/api/v1/rooms/{room['id']}/push-subscriptions", headers=auth_headers(admin))
        assert r.status_code == 204
