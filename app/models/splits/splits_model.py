from sqlalchemy import Connection, text
from app.models.splits.schemas import UnsettledExpenseRow, MemberBalanceRow


def get_unsettled_expenses(conn: Connection, room_id: int) -> list[dict]:
    rows = conn.execute(
        text("""
            SELECT id, "user", material, money, created_at
            FROM "Spendings"
            WHERE room = :room_id
              AND (settled IS NULL OR settled = FALSE)
            ORDER BY created_at DESC
        """),
        {"room_id": room_id},
    ).fetchall()
    return [UnsettledExpenseRow(**r._mapping).model_dump() for r in rows]


def get_total_pending_amount(conn: Connection, room_id: int) -> float:
    row = conn.execute(
        text("""
        SELECT sum(money)
        FROM "Spendings"
        WHERE room = :room_id
        AND (settled IS NULL or settled = FALSE)
    """),
    {"room_id": room_id}
    ).fetchone()
    return row[0] or 0


def get_member_balances(conn: Connection, room_id: int) -> list[dict]:
    rows = conn.execute(
        text("""
            SELECT u.email AS user_email, u.name, u.profile, rbs.pending_amount
            FROM "RoomBalanceSummary" rbs
            JOIN "Users" u ON u.id = rbs.user_id
            WHERE rbs.room_id = :room_id AND rbs.settled_at IS NULL
            ORDER BY rbs.pending_amount DESC
        """),
        {"room_id": room_id},
    ).fetchall()
    return [MemberBalanceRow(**r._mapping).model_dump() for r in rows]


def get_pending_for_user(conn: Connection, room_id: int, user_email: str) -> float:
    row = conn.execute(
        text("""
            SELECT rbs.pending_amount
            FROM "RoomBalanceSummary" rbs
            JOIN "Users" u ON u.id = rbs.user_id
            WHERE rbs.room_id = :room_id AND u.email = :email AND rbs.settled_at IS NULL
        """),
        {"room_id": room_id, "email": user_email},
    ).fetchone()
    return round(float(row.pending_amount), 2) if row else 0.0


def settle_all_room(conn: Connection, room_id: int) -> None:
    conn.execute(
        text("""
            UPDATE "RoomBalanceSummary" SET settled_at = NOW()
            WHERE room_id = :room_id AND settled_at IS NULL
        """),
        {"room_id": room_id},
    )
    conn.execute(
        text("""
            INSERT INTO "RoomBalanceSummary" (room_id, user_id, pending_amount, settled_at, updated_at)
            SELECT room_id, user_id, 0, NULL, NOW() FROM "UserRooms" WHERE room_id = :room_id
        """),
        {"room_id": room_id},
    )
    conn.execute(
        text("""
            UPDATE "Spendings" SET settled = TRUE, settled_at = NOW()
            WHERE room = :room_id AND (settled IS NULL OR settled = FALSE)
        """),
        {"room_id": room_id},
    )
