from fastapi import HTTPException
from sqlalchemy import Connection
from app.models.expenses.expenses_model import (
    get_expenses,
    insert_expense,
    get_expense_by_id,
    update_expense,
    delete_expense,
)
from app.models.members.members_model import get_member_by_user_id


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


def add_expense(conn: Connection, room_id: int, material: str, money: float, current_user: dict, created_at=None) -> dict:
    if money <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than 0")
    return insert_expense(conn, room_id, current_user["id"], current_user["email"], material, money, created_at)


def add_expense_for_member(
    conn: Connection, room_id: int, material: str, money: float, user_id: int, created_at=None
) -> dict:
    if money <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than 0")
    member = get_member_by_user_id(conn, room_id, user_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    return insert_expense(conn, room_id, user_id, member["email"], material, money, created_at)


def edit_expense(
    conn: Connection,
    room_id: int,
    expense_id: int,
    material: str | None,
    money: float | None,
    created_at,
    admin_user: dict,
) -> dict:
    if money is not None and money <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than 0")

    expense = get_expense_by_id(conn, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    if expense["room"] != room_id:
        raise HTTPException(status_code=404, detail="Expense does not belong to this room")

    if material is None and money is None and created_at is None:
        raise HTTPException(status_code=400, detail="Nothing to update")

    updated = update_expense(conn, expense_id, material, money, created_at)

    return updated


def remove_expense(
    conn: Connection,
    room_id: int,
    expense_id: int,
    admin_user: dict,
) -> None:
    expense = get_expense_by_id(conn, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    if expense["room"] != room_id:
        raise HTTPException(status_code=404, detail="Expense does not belong to this room")

    delete_expense(conn, expense_id)
