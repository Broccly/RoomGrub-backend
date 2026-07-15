from sqlalchemy import Connection, text
from app.models.rooms.schemas import (
    InsertRoomResponse,
    ListRoomsResponse,
    RecentExpenseRow,
    MemberStatRow,
)


def insert_room(conn: Connection) -> dict:
    row = conn.execute(
        text('INSERT INTO "Rooms" DEFAULT VALUES RETURNING id'),
    ).fetchone()
    return InsertRoomResponse(**row._mapping).model_dump()


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
            SELECT r.id,
                   (SELECT COUNT(*) FROM "UserRooms" WHERE room_id = r.id) AS members,
                   (SELECT u.email FROM "UserRooms" ur2 JOIN "Users" u ON u.id = ur2.user_id
                    WHERE ur2.room_id = r.id AND ur2.role = 'Admin' LIMIT 1) AS admin
            FROM "Rooms" r
            JOIN "UserRooms" ur ON ur.room_id = r.id
            WHERE ur.user_id = :user_id
            ORDER BY r.id DESC
        """),
        {"user_id": user_id},
    ).fetchall()
    return [ListRoomsResponse(**r._mapping).model_dump() for r in rows]


def get_room_by_id(conn: Connection, room_id: int) -> dict | None:
    row = conn.execute(
        text("""
            SELECT r.id,
                   (SELECT COUNT(*) FROM "UserRooms" WHERE room_id = r.id) AS members,
                   (SELECT u.email FROM "UserRooms" ur2 JOIN "Users" u ON u.id = ur2.user_id
                    WHERE ur2.room_id = r.id AND ur2.role = 'Admin' LIMIT 1) AS admin
            FROM "Rooms" r WHERE r.id = :room_id
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


def get_recent_expenses(conn: Connection, room_id: int, limit: int = 5) -> list[dict]:
    rows = conn.execute(
        text("""
            SELECT id, material, money, "user", created_at
            FROM "Spendings"
            WHERE room = :room_id
            ORDER BY created_at DESC
            LIMIT :limit
        """),
        {"room_id": room_id, "limit": limit},
    ).fetchall()
    return [RecentExpenseRow(**r._mapping).model_dump() for r in rows]


def get_member_stats(conn: Connection, room_id: int) -> list[dict]:
    rows = conn.execute(
        text("""
            SELECT
                u.id AS user_id,
                u.email,
                u.name,
                ur.role,
                COALESCE(SUM(s.money), 0) AS total_spent,
                COALESCE(SUM(CASE WHEN s.settled IS NOT TRUE THEN s.money ELSE 0 END), 0) AS pending_amount
            FROM "UserRooms" ur
            JOIN "Users" u ON u.id = ur.user_id
            LEFT JOIN "Spendings" s ON s."user" = u.email AND s.room = ur.room_id
            WHERE ur.room_id = :room_id
            GROUP BY u.id, u.email, u.name, ur.role
            ORDER BY total_spent DESC
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
    conn.execute(text("DELETE FROM balance WHERE room = :id"), {"id": room_id})
    conn.execute(text('DELETE FROM "Spendings" WHERE room = :id'), {"id": room_id})
    conn.execute(text('DELETE FROM "Invite" WHERE room = :id'), {"id": room_id})
    conn.execute(text("DELETE FROM push_subscriptions WHERE room_id = :id"), {"id": room_id})
    conn.execute(text("DELETE FROM notifications WHERE room_id = :id"), {"id": room_id})
    conn.execute(text('DELETE FROM "UserRooms" WHERE room_id = :id'), {"id": room_id})
    conn.execute(text('DELETE FROM "Rooms" WHERE id = :id'), {"id": room_id})
