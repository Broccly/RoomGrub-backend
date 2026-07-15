from sqlalchemy import Connection, text
from app.models.expenses.schemas import ExpenseRow


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
            FROM "Spendings"
            WHERE {where}
            ORDER BY id DESC
            LIMIT :limit
        """),
        params,
    ).fetchall()
    return [ExpenseRow(**r._mapping).model_dump() for r in rows]


def get_expense_by_id(conn: Connection, expense_id: int) -> dict | None:
    row = conn.execute(
        text("""
            SELECT id, room, "user", material, money, created_at, settled
            FROM "Spendings" WHERE id = :expense_id
        """),
        {"expense_id": expense_id},
    ).fetchone()
    return ExpenseRow(**row._mapping).model_dump() if row else None


def update_expense(
    conn: Connection,
    expense_id: int,
    material: str | None,
    money: float | None,
    created_at,
) -> dict:
    fields = []
    params: dict = {"expense_id": expense_id}
    if material is not None:
        fields.append("material = :material")
        params["material"] = material
    if money is not None:
        fields.append("money = :money")
        params["money"] = money
    if created_at is not None:
        fields.append("created_at = :created_at")
        params["created_at"] = created_at

    row = conn.execute(
        text(f"""
            UPDATE "Spendings" SET {', '.join(fields)}
            WHERE id = :expense_id
            RETURNING id, room, "user", material, money, created_at, settled
        """),
        params,
    ).fetchone()
    return ExpenseRow(**row._mapping).model_dump()


def delete_expense(conn: Connection, expense_id: int) -> None:
    conn.execute(
        text('DELETE FROM "Spendings" WHERE id = :expense_id'),
        {"expense_id": expense_id},
    )


def insert_expense(
    conn: Connection, room_id: int, user_email: str, material: str, money: float, created_at=None
) -> dict:
    row = conn.execute(
        text("""
            INSERT INTO "Spendings" (room, "user", material, money, created_at)
            VALUES (:room_id, :user_email, :material, :money, COALESCE(:created_at, NOW()))
            RETURNING id, room, "user", material, money, created_at, settled
        """),
        {"room_id": room_id, "user_email": user_email, "material": material, "money": money, "created_at": created_at},
    ).fetchone()
    return ExpenseRow(**row._mapping).model_dump()
