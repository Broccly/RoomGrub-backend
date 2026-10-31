from sqlalchemy import Connection, text
from app.models.rooms.schemas import (
    InsertRoomResponse,
    ListRoomsResponse,
    MemberPreviewRow,
    MemberStatRow,
)


def insert_room(conn: Connection, name: str | None) -> dict:
    row = conn.execute(
        text('INSERT INTO "Rooms" (name) VALUES (:name) RETURNING id, name'),
        {"name": name},
    ).fetchone()
    return InsertRoomResponse(**row._mapping).model_dump()


def update_room_name(conn: Connection, room_id: int, name: str) -> bool:
    row = conn.execute(
        text('UPDATE "Rooms" SET name = :name WHERE id = :room_id RETURNING id'),
        {"name": name, "room_id": room_id},
    ).fetchone()
    return row is not None


def insert_user_room(conn: Connection, user_id: int, room_id: int, role: str = "Admin") -> None:
    conn.execute(
        text("""
            INSERT INTO "UserRooms" (user_id, room_id, role, joined_at)
            VALUES (:user_id, :room_id, :role, NOW())
        """),
        {"user_id": user_id, "room_id": room_id, "role": role},
    )


def get_rooms_for_user(conn: Connection, user_id: int) -> list[dict]:
    rows = conn.execute(
        text("""
            SELECT r.id, r.name,
                   (SELECT COUNT(*) FROM "UserRooms" WHERE room_id = r.id) AS members,
                   a.email AS admin, a.id AS admin_user_id, a.name AS admin_name
            FROM "Rooms" r
            JOIN "UserRooms" ur ON ur.room_id = r.id
            LEFT JOIN LATERAL (
                -- The longest-standing Admin, so the three admin fields describe one person.
                SELECT u.id, u.email, u.name
                FROM "UserRooms" ur2 JOIN "Users" u ON u.id = ur2.user_id
                WHERE ur2.room_id = r.id AND ur2.role = 'Admin'
                ORDER BY ur2.joined_at, ur2.id
                LIMIT 1
            ) a ON TRUE
            WHERE ur.user_id = :user_id
            ORDER BY r.id DESC
        """),
        {"user_id": user_id},
    ).fetchall()
    return [ListRoomsResponse(**r._mapping).model_dump() for r in rows]


def get_member_previews(conn: Connection, room_ids: list[int], per_room: int = 4) -> list[dict]:
    """The first `per_room` members of each room, by join date."""
    if not room_ids:
        return []
    rows = conn.execute(
        text("""
            SELECT room_id, profile, label
            FROM (
                SELECT ur.room_id, u.profile,
                       COALESCE(NULLIF(u.name, ''), u.email) AS label,
                       ROW_NUMBER() OVER (PARTITION BY ur.room_id ORDER BY ur.joined_at, ur.id) AS rn
                FROM "UserRooms" ur
                JOIN "Users" u ON u.id = ur.user_id
                WHERE ur.room_id = ANY(:room_ids)
            ) ranked
            WHERE rn <= :per_room
            ORDER BY room_id, rn
        """),
        {"room_ids": room_ids, "per_room": per_room},
    ).fetchall()
    return [MemberPreviewRow(**r._mapping).model_dump() for r in rows]


def get_room_by_id(conn: Connection, room_id: int) -> dict | None:
    row = conn.execute(
        text("""
            SELECT r.id, r.name,
                   (SELECT COUNT(*) FROM "UserRooms" WHERE room_id = r.id) AS members,
                   a.email AS admin, a.id AS admin_user_id, a.name AS admin_name
            FROM "Rooms" r
            LEFT JOIN LATERAL (
                SELECT u.id, u.email, u.name
                FROM "UserRooms" ur2 JOIN "Users" u ON u.id = ur2.user_id
                WHERE ur2.room_id = r.id AND ur2.role = 'Admin'
                ORDER BY ur2.joined_at, ur2.id
                LIMIT 1
            ) a ON TRUE
            WHERE r.id = :room_id
        """),
        {"room_id": room_id},
    ).fetchone()
    return ListRoomsResponse(**row._mapping).model_dump() if row else None


def get_total_spent(conn: Connection, room_id: int) -> float:
    row = conn.execute(
        text("""
            SELECT COALESCE(SUM(money), 0) AS total
            FROM "Spendings"
            WHERE room = :room_id
        """),
        {"room_id": room_id},
    ).fetchone()
    return float(row.total)


def get_pending_amount(conn: Connection, room_id: int) -> float:
    row = conn.execute(
        text("""
            SELECT COALESCE(SUM(money), 0) AS pending
            FROM "Spendings"
            WHERE room = :room_id
              AND (settled IS NULL OR settled = FALSE)
        """),
        {"room_id": room_id},
    ).fetchone()
    return max(0.0, float(row.pending))


def get_member_stats(conn: Connection, room_id: int) -> list[dict]:
    rows = conn.execute(
        text("""
            SELECT
                u.id AS user_id,
                u.name,
                u.profile,
                COALESCE(SUM(CASE WHEN s.settled IS NOT TRUE THEN s.money ELSE 0 END), 0) AS pending_amount
            FROM "UserRooms" ur
            JOIN "Users" u ON u.id = ur.user_id
            LEFT JOIN "Spendings" s ON s.user_id = u.id AND s.room = ur.room_id
            WHERE ur.room_id = :room_id
            GROUP BY u.id, u.name, u.profile
            ORDER BY pending_amount DESC
        """),
        {"room_id": room_id},
    ).fetchall()
    return [MemberStatRow(**r._mapping).model_dump() for r in rows]


def count_unsettled_expenses(conn: Connection, room_id: int) -> int:
    row = conn.execute(
        text("""
            SELECT COUNT(*) AS cnt
            FROM "Spendings"
            WHERE room = :room_id
              AND (settled IS NULL OR settled = FALSE)
        """),
        {"room_id": room_id},
    ).fetchone()
    return row.cnt


def delete_room_cascade(conn: Connection, room_id: int) -> None:
    conn.execute(text('DELETE FROM "Spendings" WHERE room = :id'), {"id": room_id})
    conn.execute(text('DELETE FROM "Invite" WHERE room = :id'), {"id": room_id})
    conn.execute(text("DELETE FROM notifications WHERE room_id = :id"), {"id": room_id})
    conn.execute(text('DELETE FROM "UserRooms" WHERE room_id = :id'), {"id": room_id})
    conn.execute(text('DELETE FROM "Rooms" WHERE id = :id'), {"id": room_id})
