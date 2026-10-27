from sqlalchemy import Connection, text
from app.models.expenses.schemas import ExpenseRow, FrequentItemRow


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
    conditions = ["s.room = :room_id"]
    params: dict = {"room_id": room_id, "limit": limit}

    if cursor is not None:
        conditions.append("s.id < :cursor")
        params["cursor"] = cursor

    if settled is not None:
        if settled:
            conditions.append("s.settled = TRUE")
        else:
            conditions.append("(s.settled IS NULL OR s.settled = FALSE)")

    if search:
        conditions.append("s.material ILIKE :search")
        params["search"] = f"%{search}%"

    if user_email:
        conditions.append('s."user" = :user_email')
        params["user_email"] = user_email

    if date_from:
        conditions.append("s.created_at >= :date_from")
        params["date_from"] = date_from

    if date_to:
        conditions.append("s.created_at <= :date_to")
        params["date_to"] = date_to

    where = " AND ".join(conditions)
    rows = conn.execute(
        text(f"""
            SELECT s.id, s.room, s.user_id,
                   COALESCE(NULLIF(u.name, ''), s."user") AS "user",
                   s.material, s.money, s.created_at, s.settled,
                   u.name AS user_name, u.profile AS user_profile, s.settled_at
            FROM "Spendings" s
            LEFT JOIN "Users" u ON u.email = s."user"
            WHERE {where}
            ORDER BY s.id DESC
            LIMIT :limit
        """),
        params,
    ).fetchall()
    return [ExpenseRow(**r._mapping).model_dump() for r in rows]


def get_expense_by_id(conn: Connection, expense_id: int) -> dict | None:
    row = conn.execute(
        text("""
            SELECT s.id, s.room, s.user_id,
                   COALESCE(NULLIF(u.name, ''), s."user") AS "user",
                   s.material, s.money, s.created_at, s.settled,
                   u.name AS user_name, u.profile AS user_profile, s.settled_at
            FROM "Spendings" s
            LEFT JOIN "Users" u ON u.email = s."user"
            WHERE s.id = :expense_id
        """),
        {"expense_id": expense_id},
    ).fetchone()
    return ExpenseRow(**row._mapping).model_dump() if row else None


def get_frequent_items(conn: Connection, room_id: int, limit: int, window: int = 100) -> list[str]:
    """Most-used item names across the room's latest `window` expenses.

    `material` can hold several comma-separated items. Names are grouped
    case-insensitively and shown with their latest spelling; ties go to the
    most recently used.
    """
    rows = conn.execute(
        text("""
            WITH recent AS (
                SELECT id, material
                FROM "Spendings"
                WHERE room = :room_id
                ORDER BY id DESC
                LIMIT :window
            ),
            parts AS (
                SELECT r.id, btrim(part) AS label
                FROM recent r, regexp_split_to_table(r.material, ',') AS part
            )
            SELECT (array_agg(label ORDER BY id DESC))[1] AS label
            FROM parts
            WHERE label <> ''
            GROUP BY lower(label)
            ORDER BY COUNT(*) DESC, MAX(id) DESC
            LIMIT :limit
        """),
        {"room_id": room_id, "window": window, "limit": limit},
    ).fetchall()
    return [FrequentItemRow(**r._mapping).label for r in rows]


def update_expense(
    conn: Connection,
    expense_id: int,
    material: str | None,
    money: float | None,
    created_at,
) -> dict | None:
    """Update an unsettled expense. Returns None, changing nothing, if it is settled."""
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
            WHERE id = :expense_id AND settled IS NOT TRUE
            RETURNING id
        """),
        params,
    ).fetchone()
    return get_expense_by_id(conn, expense_id) if row else None


def delete_expense(conn: Connection, expense_id: int) -> bool:
    """Delete an unsettled expense. Returns False, deleting nothing, if it is settled."""
    row = conn.execute(
        text('DELETE FROM "Spendings" WHERE id = :expense_id AND settled IS NOT TRUE RETURNING id'),
        {"expense_id": expense_id},
    ).fetchone()
    return row is not None


def lock_expense(conn: Connection, expense_id: int) -> None:
    """Row-lock the expense until commit, so a concurrent settle-all can't settle it mid-change."""
    conn.execute(
        text('SELECT id FROM "Spendings" WHERE id = :expense_id FOR UPDATE'),
        {"expense_id": expense_id},
    )


def insert_expense(
    conn: Connection, room_id: int, user_id: int, user_email: str, material: str, money: float, created_at=None
) -> dict:
    row = conn.execute(
        text("""
            INSERT INTO "Spendings" (room, user_id, "user", material, money, created_at)
            VALUES (:room_id, :user_id, :user_email, :material, :money, COALESCE(:created_at, NOW()))
            RETURNING id
        """),
        {
            "room_id": room_id,
            "user_id": user_id,
            "user_email": user_email,
            "material": material,
            "money": money,
            "created_at": created_at,
        },
    ).fetchone()
    return get_expense_by_id(conn, row.id)


def insert_spending_splits(conn: Connection, spending_id: int, splits: list[dict]) -> None:
    if not splits:
        return
    conn.execute(
        text("""
            INSERT INTO "SpendingSplits" (spending_id, user_id, amount_paid, amount_owed)
            VALUES (:spending_id, :user_id, :amount_paid, :amount_owed)
        """),
        [{"spending_id": spending_id, **s} for s in splits],
    )


def get_expense_splits(conn: Connection, spending_id: int) -> list[dict]:
    rows = conn.execute(
        text("""
            SELECT user_id, amount_paid, amount_owed
            FROM "SpendingSplits"
            WHERE spending_id = :spending_id
        """),
        {"spending_id": spending_id},
    ).fetchall()
    return [dict(r._mapping) for r in rows]


def delete_spending_splits(conn: Connection, spending_id: int) -> None:
    conn.execute(
        text('DELETE FROM "SpendingSplits" WHERE spending_id = :spending_id'),
        {"spending_id": spending_id},
    )


def get_expense_participants(conn: Connection, spending_id: int) -> list[dict]:
    rows = conn.execute(
        text("""
            SELECT ss.user_id, u.name, u.profile, ss.amount_paid, ss.amount_owed
            FROM "SpendingSplits" ss
            JOIN "Users" u ON u.id = ss.user_id
            WHERE ss.spending_id = :spending_id
            ORDER BY ss.user_id
        """),
        {"spending_id": spending_id},
    ).fetchall()
    return [dict(r._mapping) for r in rows]


def upsert_room_balance_summary_delta(conn: Connection, room_id: int, user_id: int, delta: float) -> None:
    conn.execute(
        text("""
            INSERT INTO "RoomBalanceSummary" (room_id, user_id, pending_amount, settled_at, updated_at)
            VALUES (:room_id, :user_id, :delta, NULL, NOW())
            ON CONFLICT (room_id, user_id) WHERE settled_at IS NULL
            DO UPDATE SET
                pending_amount = "RoomBalanceSummary".pending_amount + EXCLUDED.pending_amount,
                updated_at = NOW()
        """),
        {"room_id": room_id, "user_id": user_id, "delta": delta},
    )
