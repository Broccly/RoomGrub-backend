from sqlalchemy import Connection
from app.models.notifications.notifications_model import (
    insert_notification,
    get_notifications,
    upsert_fcm_token,
    delete_fcm_token
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


def register_push(conn: Connection, user_id: int, fcm_token: str, platform: str) -> None:
    upsert_fcm_token(conn, user_id, fcm_token, platform = platform)


def unregister_push(conn: Connection, user_id: int, fcm_token: str) -> None:
    delete_fcm_token(conn, user_id, fcm_token)
