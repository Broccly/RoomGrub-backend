from sqlalchemy import Connection, text


def get_members(conn: Connection, room_id: int) -> list[dict]:
    rows = conn.execute(
        text("""
            SELECT ur.id, u.id AS user_id, u.email, u.name, ur.role, ur.joined_at
            FROM "UserRooms" ur
            JOIN "Users" u ON u.id = ur.user_id
            WHERE ur.room_id = :room_id
            ORDER BY ur.joined_at ASC
        """),
        {"room_id": room_id},
    ).fetchall()
    return [dict(r._mapping) for r in rows]


def get_member_by_id(conn: Connection, room_id: int, member_id: int) -> dict | None:
    row = conn.execute(
        text("""
            SELECT ur.id, u.id AS user_id, u.email, u.name, ur.role, ur.joined_at
            FROM "UserRooms" ur
            JOIN "Users" u ON u.id = ur.user_id
            WHERE ur.room_id = :room_id AND ur.id = :member_id
        """),
        {"room_id": room_id, "member_id": member_id},
    ).fetchone()
    return dict(row._mapping) if row else None


def get_member_expenses(conn: Connection, room_id: int, user_email: str) -> list[dict]:
    rows = conn.execute(
        text("""
            SELECT id, material, money, created_at, settled
            FROM "Spendings"
            WHERE room = :room_id AND "user" = :email
            ORDER BY created_at DESC
        """),
        {"room_id": room_id, "email": user_email},
    ).fetchall()
    return [dict(r._mapping) for r in rows]


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


def update_member_role(conn: Connection, room_id: int, member_id: int, role: str) -> None:
    conn.execute(
        text('UPDATE "UserRooms" SET role = :role WHERE id = :member_id AND room_id = :room_id'),
        {"role": role, "member_id": member_id, "room_id": room_id},
    )


def remove_user_room(conn: Connection, room_id: int, member_id: int) -> None:
    conn.execute(
        text('DELETE FROM "UserRooms" WHERE id = :member_id AND room_id = :room_id'),
        {"member_id": member_id, "room_id": room_id},
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
    return dict(row._mapping) if row else None


def insert_balance_debit(conn: Connection, room_id: int, user_email: str, amount: float) -> None:
    conn.execute(
        text("""
            INSERT INTO Balance (room, "user", amount, status, created_at)
            VALUES (:room_id, :user_email, :amount, 'debit', NOW())
        """),
        {"room_id": room_id, "user_email": user_email, "amount": -abs(amount)},
    )


def insert_balance_credit(conn: Connection, room_id: int, user_email: str, amount: float) -> None:
    conn.execute(
        text("""
            INSERT INTO Balance (room, "user", amount, status, created_at)
            VALUES (:room_id, :user_email, :amount, 'credit', NOW())
        """),
        {"room_id": room_id, "user_email": user_email, "amount": abs(amount)},
    )
