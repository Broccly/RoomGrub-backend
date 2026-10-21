from datetime import datetime

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
    """Every current member, plus anyone who left with a non-zero active balance."""
    rows = conn.execute(
        text("""
            WITH people AS (
                SELECT ur.user_id, ur.role
                FROM "UserRooms" ur
                WHERE ur.room_id = :room_id
                UNION
                SELECT rbs.user_id, NULL
                FROM "RoomBalanceSummary" rbs
                WHERE rbs.room_id = :room_id
                  AND rbs.settled_at IS NULL
                  AND ABS(rbs.pending_amount) > 0.005
                  AND NOT EXISTS (
                      SELECT 1 FROM "UserRooms" ur2
                      WHERE ur2.room_id = :room_id AND ur2.user_id = rbs.user_id
                  )
            ),
            spend AS (
                SELECT user_id,
                       SUM(money) AS total_spent,
                       SUM(money) FILTER (WHERE settled IS NOT TRUE) AS unsettled_spent
                FROM "Spendings"
                WHERE room = :room_id
                GROUP BY user_id
            ),
            share AS (
                SELECT ss.user_id, SUM(ss.amount_owed) AS unsettled_share
                FROM "SpendingSplits" ss
                JOIN "Spendings" s ON s.id = ss.spending_id
                WHERE s.room = :room_id AND s.settled IS NOT TRUE
                GROUP BY ss.user_id
            )
            SELECT u.id AS user_id,
                   u.email AS user_email,
                   u.name,
                   u.profile,
                   p.role,
                   COALESCE(rbs.pending_amount, 0) AS pending_amount,
                   COALESCE(sp.unsettled_spent, 0) AS unsettled_spent,
                   COALESCE(sh.unsettled_share, 0) AS unsettled_share,
                   COALESCE(sp.total_spent, 0) AS total_spent
            FROM people p
            JOIN "Users" u ON u.id = p.user_id
            LEFT JOIN "RoomBalanceSummary" rbs
                   ON rbs.room_id = :room_id AND rbs.user_id = p.user_id AND rbs.settled_at IS NULL
            LEFT JOIN spend sp ON sp.user_id = p.user_id
            LEFT JOIN share sh ON sh.user_id = p.user_id
            ORDER BY pending_amount DESC, u.id
        """),
        {"room_id": room_id},
    ).fetchall()
    return [MemberBalanceRow(**r._mapping).model_dump() for r in rows]


def get_last_settled_at(conn: Connection, room_id: int) -> datetime | None:
    return conn.execute(
        text("""
            SELECT MAX(settled_at)
            FROM "RoomBalanceSummary"
            WHERE room_id = :room_id
        """),
        {"room_id": room_id},
    ).scalar()


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
