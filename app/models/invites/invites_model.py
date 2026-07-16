from sqlalchemy import Connection, text
from app.models.invites.schemas import InviteByTokenRow


def insert_invite(conn: Connection, room_id: int, invited_by_id: int) -> str:
    row = conn.execute(
        text("""
            INSERT INTO "Invite" (room, invited_by, token, status, created_at, updated_at)
            VALUES (:room_id, :invited_by, gen_random_uuid(), 'pending', NOW(), NOW())
            RETURNING token::text
        """),
        {"room_id": room_id, "invited_by": invited_by_id},
    ).fetchone()
    return row.token


def get_invite_by_token(conn: Connection, token: str) -> dict | None:
    row = conn.execute(
        text("""
            SELECT
                i.token::text,
                i.room AS room_id,
                i.status,
                i.created_at,
                u.email AS invited_by_email,
                u.name AS invited_by_name,
                u.profile AS invited_by_profile
            FROM "Invite" i
            JOIN "Users" u ON u.id = i.invited_by
            WHERE i.token::text = :token
        """),
        {"token": token},
    ).fetchone()
    return InviteByTokenRow(**row._mapping).model_dump() if row else None


def update_invite_status(conn: Connection, token: str, status: str) -> None:
    conn.execute(
        text('UPDATE "Invite" SET status = :status, updated_at = NOW() WHERE token::text = :token'),
        {"status": status, "token": token},
    )


def check_membership(conn: Connection, user_id: int, room_id: int) -> bool:
    row = conn.execute(
        text('SELECT id FROM "UserRooms" WHERE user_id = :user_id AND room_id = :room_id'),
        {"user_id": user_id, "room_id": room_id},
    ).fetchone()
    return row is not None


def insert_member(conn: Connection, user_id: int, room_id: int) -> None:
    conn.execute(
        text("""
            INSERT INTO "UserRooms" (user_id, room_id, role, joined_at)
            VALUES (:user_id, :room_id, 'Member', NOW())
        """),
        {"user_id": user_id, "room_id": room_id},
    )
