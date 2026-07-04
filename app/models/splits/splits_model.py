from sqlalchemy import Connection, text


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
    return [dict(r._mapping) for r in rows]


def get_member_balances(conn: Connection, room_id: int) -> list[dict]:
    rows = conn.execute(
        text("""
            SELECT
                u.email AS user_email,
                u.name,
                COALESCE(SUM(CASE WHEN s.settled IS NOT TRUE THEN s.money ELSE 0 END), 0) AS pending_amount
            FROM UserRooms ur
            JOIN Users u ON u.id = ur.user_id
            LEFT JOIN Spendings s ON s."user" = u.email AND s.room = ur.room_id
            WHERE ur.room_id = :room_id
            GROUP BY u.email, u.name
            ORDER BY pending_amount DESC
        """),
        {"room_id": room_id},
    ).fetchall()
    return [dict(r._mapping) for r in rows]


def get_pending_for_user(conn: Connection, room_id: int, user_email: str) -> float:
    row = conn.execute(
        text("""
            SELECT COALESCE(SUM(money), 0) AS pending
            FROM Spendings
            WHERE room = :room_id
              AND "user" = :email
              AND (settled IS NULL OR settled = FALSE)
        """),
        {"room_id": room_id, "email": user_email},
    ).fetchone()
    return max(0.0, float(row.pending))


def settle_user_expenses(conn: Connection, room_id: int, user_email: str) -> None:
    unsettled = conn.execute(
        text("""
            SELECT id, money FROM Spendings
            WHERE room = :room_id AND "user" = :email
              AND (settled IS NULL OR settled = FALSE)
        """),
        {"room_id": room_id, "email": user_email},
    ).fetchall()

    for expense in unsettled:
        conn.execute(
            text("""
                INSERT INTO Balance (room, "user", amount, status, spending_id, created_at)
                VALUES (:room_id, :email, :amount, 'debit', :spending_id, NOW())
            """),
            {
                "room_id": room_id,
                "email": user_email,
                "amount": -abs(expense.money),
                "spending_id": expense.id,
            },
        )

    if unsettled:
        ids = [e.id for e in unsettled]
        conn.execute(
            text(f"UPDATE Spendings SET settled = TRUE WHERE id = ANY(:ids)"),
            {"ids": ids},
        )
