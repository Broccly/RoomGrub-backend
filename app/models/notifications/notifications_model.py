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

def upsert_fcm_token(conn: Connection, user_id: int, fcm_token: str, platform: str = "android") -> None:
    conn.execute(
        text("""
            INSERT INTO fcm_tokens (user_id, fcm_token, platform, created_at, updated_at)
            VALUES (:user_id, :fcm_token, :platform, NOW(), NOW())
            ON CONFLICT (fcm_token) DO UPDATE
              SET user_id = EXCLUDED.user_id,
                  platform = EXCLUDED.platform,
                  updated_at = NOW()
        """),
        {
            "user_id": user_id,
            "fcm_token": fcm_token,
            "platform": platform
        }
    )

def delete_fcm_token(conn: Connection, user_id: int, fcm_token: str) -> None:
    conn.execute(
        text("""
            DELETE FROM fcm_tokens WHERE user_id = :user_id AND fcm_token = :fcm_token
        """),
        { "user_id": user_id, "fcm_token": fcm_token }
    )

def get_fcm_tokens_for_users(conn: Connection, user_ids: list[int]) -> list[str]:
    rows = conn.execute(
        text("SELECT fcm_token FROM fcm_tokens WHERE user_id = ANY(:user_ids)"),
        {"user_ids": user_ids},
    ).fetchall()
    return [r.fcm_token for r in rows]


def delete_fcm_tokens(conn: Connection, fcm_tokens: list[str]) -> None:
    conn.execute(
        text("DELETE FROM fcm_tokens WHERE fcm_token = ANY(:fcm_tokens)"),
        {"fcm_tokens": fcm_tokens},
    )
