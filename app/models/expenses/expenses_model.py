from sqlalchemy import Connection, text


def get_expenses(
    conn: Connection,
    room_id: int,
    cursor: int | None = None,
    limit: int = 20,
    settled: bool | None = None,
    search: str | None = None,
    user_email: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    conditions = ["room = :room_id"]
    params: dict = {"room_id": room_id, "limit": limit}

    if cursor is not None:
        conditions.append("id < :cursor")
        params["cursor"] = cursor

    if settled is not None:
        if settled:
            conditions.append("settled = TRUE")
        else:
            conditions.append("(settled IS NULL OR settled = FALSE)")

    if search:
        conditions.append("material ILIKE :search")
        params["search"] = f"%{search}%"

    if user_email:
        conditions.append('"user" = :user_email')
        params["user_email"] = user_email

    if date_from:
        conditions.append("created_at >= :date_from")
        params["date_from"] = date_from

    if date_to:
        conditions.append("created_at <= :date_to")
        params["date_to"] = date_to

    where = " AND ".join(conditions)
    rows = conn.execute(
        text(f"""
            SELECT id, room, "user", material, money, created_at, settled
            FROM Spendings
            WHERE {where}
            ORDER BY id DESC
            LIMIT :limit
        """),
        params,
    ).fetchall()
    return [dict(r._mapping) for r in rows]


def insert_expense(
    conn: Connection, room_id: int, user_email: str, material: str, money: float
) -> dict:
    row = conn.execute(
        text("""
            INSERT INTO Spendings (room, "user", material, money, created_at)
            VALUES (:room_id, :user_email, :material, :money, NOW())
            RETURNING id, room, "user", material, money, created_at, settled
        """),
        {"room_id": room_id, "user_email": user_email, "material": material, "money": money},
    ).fetchone()
    return dict(row._mapping)
