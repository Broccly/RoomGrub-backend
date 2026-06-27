from fastapi import HTTPException
from sqlalchemy import Connection
from app.models.expenses.expenses_model import get_expenses, insert_expense


def list_expenses(
    conn: Connection,
    room_id: int,
    cursor: int | None,
    limit: int,
    settled: bool | None,
    search: str | None,
    user_email: str | None,
    date_from: str | None,
    date_to: str | None,
) -> dict:
    items = get_expenses(
        conn, room_id, cursor=cursor, limit=limit,
        settled=settled, search=search, user_email=user_email,
        date_from=date_from, date_to=date_to,
    )
    next_cursor = items[-1]["id"] if len(items) == limit else None
    return {"items": items, "next_cursor": next_cursor}


def add_expense(conn: Connection, room_id: int, material: str, money: float, current_user: dict) -> dict:
    if money <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than 0")
    return insert_expense(conn, room_id, current_user["email"], material, money)


def add_expense_for_member(
    conn: Connection, room_id: int, material: str, money: float, user_email: str
) -> dict:
    if money <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than 0")
    return insert_expense(conn, room_id, user_email, material, money)
