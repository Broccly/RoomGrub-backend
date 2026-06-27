from sqlalchemy import Connection
from app.models.notifications.notifications_model import (
    insert_notification,
    get_notifications,
    upsert_push_subscription,
    delete_push_subscription,
)


def create_notification(
    conn: Connection,
    room_id: int,
    current_user: dict,
    activity_type: str,
    title: str,
    message: str,
    data: dict | None,
) -> dict:
    return insert_notification(
        conn, room_id=room_id, triggered_by=current_user["id"],
        activity_type=activity_type, title=title, message=message, data=data,
    )


def list_notifications(conn: Connection, room_id: int) -> list[dict]:
    return get_notifications(conn, room_id)


def register_push(conn: Connection, room_id: int, user_id: int, endpoint: str, p256dh_key: str, auth_key: str) -> None:
    upsert_push_subscription(conn, user_id, room_id, endpoint, p256dh_key, auth_key)


def unregister_push(conn: Connection, room_id: int, user_id: int) -> None:
    delete_push_subscription(conn, user_id, room_id)
