from sqlalchemy import Connection, text
from app.models.members.schemas import (
    MemberRow,
    MemberPendingExpenseRow,
    MyMembershipRow,
)


def get_members(conn: Connection, room_id: int) -> list[dict]:
    rows = conn.execute(
        text("""
            SELECT ur.id, u.id AS user_id, u.email, u.name, u.profile, ur.role, ur.joined_at
            FROM "UserRooms" ur
            JOIN "Users" u ON u.id = ur.user_id
            WHERE ur.room_id = :room_id
            ORDER BY ur.joined_at ASC
        """),
        {"room_id": room_id},
    ).fetchall()
    return [MemberRow(**r._mapping).model_dump() for r in rows]


def get_member_by_user_id(conn: Connection, room_id: int, user_id: int) -> dict | None:
    row = conn.execute(
        text("""
            SELECT ur.id, u.id AS user_id, u.email, u.name, u.profile, ur.role, ur.joined_at
            FROM "UserRooms" ur
            JOIN "Users" u ON u.id = ur.user_id
            WHERE ur.room_id = :room_id AND ur.user_id = :user_id
        """),
        {"room_id": room_id, "user_id": user_id},
    ).fetchone()
    return MemberRow(**row._mapping).model_dump() if row else None


def get_members_by_user_ids(conn: Connection, room_id: int, user_ids: list[int]) -> list[dict]:
    rows = conn.execute(
        text("""
            SELECT ur.id, u.id AS user_id, u.email, u.name, u.profile, ur.role, ur.joined_at
            FROM "UserRooms" ur
            JOIN "Users" u ON u.id = ur.user_id
            WHERE ur.room_id = :room_id AND ur.user_id = ANY(:user_ids)
        """),
        {"room_id": room_id, "user_ids": user_ids},
    ).fetchall()
    return [MemberRow(**r._mapping).model_dump() for r in rows]


def get_member_pending_expenses(conn: Connection, room_id: int, user_email: str) -> list[dict]:
    rows = conn.execute(
        text("""
            SELECT id, material, money, created_at, settled
            FROM "Spendings"
            WHERE room = :room_id AND "user" = :email
              AND (settled IS NULL OR settled = FALSE)
            ORDER BY created_at DESC
        """),
        {"room_id": room_id, "email": user_email},
    ).fetchall()
    return [MemberPendingExpenseRow(**r._mapping).model_dump() for r in rows]


def get_member_pending(conn: Connection, room_id: int, user_email: str) -> float:
    row = conn.execute(
        text("""
            SELECT COALESCE(SUM(money), 0) AS pending
            FROM "Spendings"
            WHERE room = :room_id AND "user" = :email
              AND (settled IS NULL OR settled = FALSE)
        """),
        {"room_id": room_id, "email": user_email},
    ).fetchone()
    return max(0.0, float(row.pending))


def update_member_role(conn: Connection, room_id: int, user_id: int, role: str) -> None:
    conn.execute(
        text('UPDATE "UserRooms" SET role = :role WHERE user_id = :user_id AND room_id = :room_id'),
        {"role": role, "user_id": user_id, "room_id": room_id},
    )


def remove_user_room(conn: Connection, room_id: int, user_id: int) -> None:
    conn.execute(
        text('DELETE FROM "UserRooms" WHERE user_id = :user_id AND room_id = :room_id'),
        {"user_id": user_id, "room_id": room_id},
    )


def get_my_membership(conn: Connection, room_id: int, user_id: int) -> dict | None:
    row = conn.execute(
        text("""
            SELECT ur.id, u.email, ur.role
            FROM "UserRooms" ur
            JOIN "Users" u ON u.id = ur.user_id
            WHERE ur.room_id = :room_id AND ur.user_id = :user_id
        """),
        {"room_id": room_id, "user_id": user_id},
    ).fetchone()
    return MyMembershipRow(**row._mapping).model_dump() if row else None
