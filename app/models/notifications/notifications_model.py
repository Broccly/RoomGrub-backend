import json
from sqlalchemy import Connection, text
from app.models.notifications.schemas import NotificationRow


def insert_notification(
    conn: Connection,
    room_id: int,
    triggered_by: int,
    activity_type: str,
    title: str,
    message: str,
    data: dict | None,
) -> dict:
    row = conn.execute(
        text("""
            INSERT INTO notifications (room_id, triggered_by, activity_type, title, message, data, created_at)
            VALUES (:room_id, :triggered_by, :activity_type, :title, :message, :data, NOW())
            RETURNING id, room_id, activity_type, title, message, created_at
        """),
        {
            "room_id": room_id,
            "triggered_by": triggered_by,
            "activity_type": activity_type,
            "title": title,
            "message": message,
            "data": json.dumps(data) if data else None,
        },
    ).fetchone()
    return NotificationRow(**row._mapping).model_dump()


def get_notifications(conn: Connection, room_id: int, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        text("""
            SELECT id, room_id, activity_type, title, message, created_at
            FROM notifications
            WHERE room_id = :room_id
            ORDER BY created_at DESC
            LIMIT :limit
        """),
        {"room_id": room_id, "limit": limit},
    ).fetchall()
    return [NotificationRow(**r._mapping).model_dump() for r in rows]


def upsert_push_subscription(
    conn: Connection,
    user_id: int,
    room_id: int,
    endpoint: str,
    p256dh_key: str,
    auth_key: str,
) -> None:
    conn.execute(
        text("""
            INSERT INTO push_subscriptions (user_id, room_id, endpoint, p256dh_key, auth_key, created_at, updated_at)
            VALUES (:user_id, :room_id, :endpoint, :p256dh_key, :auth_key, NOW(), NOW())
            ON CONFLICT (user_id, room_id) DO UPDATE
              SET endpoint = EXCLUDED.endpoint,
                  p256dh_key = EXCLUDED.p256dh_key,
                  auth_key = EXCLUDED.auth_key,
                  updated_at = NOW()
        """),
        {
            "user_id": user_id,
            "room_id": room_id,
            "endpoint": endpoint,
            "p256dh_key": p256dh_key,
            "auth_key": auth_key,
        },
    )


def delete_push_subscription(conn: Connection, user_id: int, room_id: int) -> None:
    conn.execute(
        text("DELETE FROM push_subscriptions WHERE user_id = :user_id AND room_id = :room_id"),
        {"user_id": user_id, "room_id": room_id},
    )
