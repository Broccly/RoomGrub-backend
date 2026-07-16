from sqlalchemy import Connection, text
from app.models.splits.schemas import (
    UnsettledExpenseRow,
    MemberBalanceMemberRow,
    FilteredUnsettledExpenseRow,
    SettleFilteredExpenseRow,
)


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


def get_member_balances(conn: Connection, room_id: int) -> list[dict]:
    members = conn.execute(
        text("""
            SELECT u.email AS user_email, u.name, u.profile
            FROM "UserRooms" ur
            JOIN "Users" u ON u.id = ur.user_id
            WHERE ur.room_id = :room_id
        """),
        {"room_id": room_id},
    ).fetchall()
    if not members:
        return []
    members = [MemberBalanceMemberRow(**m._mapping) for m in members]

    paid_rows = conn.execute(
        text("""
            SELECT "user" AS user_email, COALESCE(SUM(money), 0) AS paid
            FROM "Spendings"
            WHERE room = :room_id AND (settled IS NULL OR settled = FALSE)
            GROUP BY "user"
        """),
        {"room_id": room_id},
    ).fetchall()
    paid_by_user = {r.user_email: float(r.paid) for r in paid_rows}
    fair_share = sum(paid_by_user.values()) / len(members)

    adjustment_rows = conn.execute(
        text("""
            SELECT "user" AS user_email, COALESCE(SUM(amount), 0) AS adjustment
            FROM balance
            WHERE room = :room_id AND spending_id IS NULL
            GROUP BY "user"
        """),
        {"room_id": room_id},
    ).fetchall()
    adjustment_by_user = {r.user_email: float(r.adjustment) for r in adjustment_rows}

    result = [
        {
            "user_email": m.user_email,
            "name": m.name,
            "profile": m.profile,
            "pending_amount": round(
                paid_by_user.get(m.user_email, 0.0)
                - fair_share
                + adjustment_by_user.get(m.user_email, 0.0),
                2,
            ),
        }
        for m in members
    ]
    result.sort(key=lambda r: r["pending_amount"], reverse=True)
    return result


def get_pending_for_user(conn: Connection, room_id: int, user_email: str) -> float:
    member_count = conn.execute(
        text('SELECT COUNT(*) FROM "UserRooms" WHERE room_id = :room_id'),
        {"room_id": room_id},
    ).scalar()
    if not member_count:
        return 0.0

    total_unsettled = conn.execute(
        text("""
            SELECT COALESCE(SUM(money), 0) FROM "Spendings"
            WHERE room = :room_id AND (settled IS NULL OR settled = FALSE)
        """),
        {"room_id": room_id},
    ).scalar()

    paid = conn.execute(
        text("""
            SELECT COALESCE(SUM(money), 0) FROM "Spendings"
            WHERE room = :room_id AND "user" = :email
              AND (settled IS NULL OR settled = FALSE)
        """),
        {"room_id": room_id, "email": user_email},
    ).scalar()

    adjustment = conn.execute(
        text("""
            SELECT COALESCE(SUM(amount), 0) FROM balance
            WHERE room = :room_id AND "user" = :email AND spending_id IS NULL
        """),
        {"room_id": room_id, "email": user_email},
    ).scalar()

    fair_share = float(total_unsettled) / member_count
    return round(float(paid) - fair_share + float(adjustment), 2)


def settle_member_balance(conn: Connection, room_id: int, user_email: str, pending: float) -> None:
    status = "debit" if pending > 0 else "credit"
    conn.execute(
        text("""
            INSERT INTO balance (room, "user", amount, status, spending_id, created_at)
            VALUES (:room_id, :email, :amount, :status, NULL, NOW())
        """),
        {"room_id": room_id, "email": user_email, "amount": -pending, "status": status},
    )


def settle_all_room(conn: Connection, room_id: int) -> None:
    conn.execute(
        text("""
            UPDATE "Spendings" SET settled = TRUE
            WHERE room = :room_id AND (settled IS NULL OR settled = FALSE)
        """),
        {"room_id": room_id},
    )
    conn.execute(
        text("DELETE FROM balance WHERE room = :room_id AND spending_id IS NULL"),
        {"room_id": room_id},
    )


def get_filtered_unsettled_expenses(
    conn: Connection,
    room_id: int,
    date_from=None,
    date_to=None,
    member_emails: list[str] | None = None,
) -> list[dict]:
    rows = conn.execute(
        text("""
            SELECT id, "user", money
            FROM "Spendings"
            WHERE room = :room_id
              AND (settled IS NULL OR settled = FALSE)
              AND (CAST(:date_from AS timestamp) IS NULL OR created_at >= :date_from)
              AND (CAST(:date_to AS timestamp) IS NULL OR created_at <= :date_to)
              AND (CAST(:member_emails AS text[]) IS NULL OR "user" = ANY(:member_emails))
        """),
        {
            "room_id": room_id,
            "date_from": date_from,
            "date_to": date_to,
            "member_emails": member_emails,
        },
    ).fetchall()
    return [FilteredUnsettledExpenseRow(**r._mapping).model_dump() for r in rows]


def get_pending_for_user_filtered(
    conn: Connection,
    room_id: int,
    user_email: str,
    date_from=None,
    date_to=None,
    member_emails: list[str] | None = None,
) -> float:
    if not member_emails:
        return 0.0

    params = {
        "room_id": room_id,
        "member_emails": member_emails,
        "date_from": date_from,
        "date_to": date_to,
    }

    total_filtered = conn.execute(
        text("""
            SELECT COALESCE(SUM(money), 0) FROM "Spendings"
            WHERE room = :room_id
              AND (settled IS NULL OR settled = FALSE)
              AND "user" = ANY(:member_emails)
              AND (CAST(:date_from AS timestamp) IS NULL OR created_at >= :date_from)
              AND (CAST(:date_to AS timestamp) IS NULL OR created_at <= :date_to)
        """),
        params,
    ).scalar()

    paid = conn.execute(
        text("""
            SELECT COALESCE(SUM(money), 0) FROM "Spendings"
            WHERE room = :room_id
              AND (settled IS NULL OR settled = FALSE)
              AND "user" = ANY(:member_emails)
              AND (CAST(:date_from AS timestamp) IS NULL OR created_at >= :date_from)
              AND (CAST(:date_to AS timestamp) IS NULL OR created_at <= :date_to)
              AND "user" = :email
        """),
        {**params, "email": user_email},
    ).scalar()

    fair_share = float(total_filtered) / len(member_emails)
    return round(float(paid) - fair_share, 2)


def settle_filtered_room(conn: Connection, room_id: int, expense_ids: list[int]) -> None:
    if not expense_ids:
        return

    rows = conn.execute(
        text('SELECT id, "user", money FROM "Spendings" WHERE id = ANY(:ids) AND room = :room_id'),
        {"ids": expense_ids, "room_id": room_id},
    ).fetchall()
    rows = [SettleFilteredExpenseRow(**r._mapping) for r in rows]

    for r in rows:
        conn.execute(
            text("""
                INSERT INTO balance (room, "user", amount, status, spending_id, created_at)
                VALUES (:room_id, :email, :amount, 'debit', :spending_id, NOW())
            """),
            {"room_id": room_id, "email": r.user, "amount": -float(r.money), "spending_id": r.id},
        )

    conn.execute(
        text('UPDATE "Spendings" SET settled = TRUE WHERE id = ANY(:ids) AND room = :room_id'),
        {"ids": expense_ids, "room_id": room_id},
    )
