# from app.utils.jwt_utils import create_jwt

# # Notifications router is not mounted in main.py (see main.py), so these routes
# # 404 regardless of auth — left as-is (not part of the new coverage effort).
# _E2E_TEST_USER = dict(id=23, email="developersankar14@gmail.com", name="E2E Test User", picture=None)


# def _auth_headers() -> dict[str, str]:
#     return {"Authorization": f"Bearer {create_jwt(_E2E_TEST_USER)}"}


# ROOM_ID = 999999

# NOTIFICATION_BODY = {
#     "room_id": ROOM_ID,
#     "activity_type": "expense_added",
#     "title": "Test",
#     "message": "Test notification",
# }
# PUSH_SUBSCRIPTION_BODY = {
#     "endpoint": "https://push.example.com/sub/123",
#     "p256dh_key": "dummykey",
#     "auth_key": "dummyauth",
# }


# class TestNotificationsUnauthenticated:
#     def test_create_notification(self, test_client):
#         assert test_client.post("/api/v1/notifications", json=NOTIFICATION_BODY).status_code == 401

#     def test_list_notifications(self, test_client):
#         assert test_client.get(f"/api/v1/rooms/{ROOM_ID}/notifications").status_code == 401

#     def test_register_push(self, test_client):
#         assert test_client.post(f"/api/v1/rooms/{ROOM_ID}/push-subscriptions", json=PUSH_SUBSCRIPTION_BODY).status_code == 401

#     def test_unregister_push(self, test_client):
#         assert test_client.delete(f"/api/v1/rooms/{ROOM_ID}/push-subscriptions").status_code == 401


# class TestNotificationsAuthenticated:
#     def test_create_notification(self, test_client):
#         r = test_client.post("/api/v1/notifications", json=NOTIFICATION_BODY, headers=_auth_headers())
#         assert r.status_code != 401

#     def test_list_notifications(self, test_client):
#         r = test_client.get(f"/api/v1/rooms/{ROOM_ID}/notifications", headers=_auth_headers())
#         assert r.status_code != 401

#     def test_register_push(self, test_client):
#         r = test_client.post(f"/api/v1/rooms/{ROOM_ID}/push-subscriptions", json=PUSH_SUBSCRIPTION_BODY, headers=_auth_headers())
#         assert r.status_code != 401

#     def test_unregister_push(self, test_client):
#         r = test_client.delete(f"/api/v1/rooms/{ROOM_ID}/push-subscriptions", headers=_auth_headers())
#         assert r.status_code != 401
