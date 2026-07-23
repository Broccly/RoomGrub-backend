from fastapi import HTTPException
from sqlalchemy import Connection
from app.models.expenses.expenses_model import (
    get_expenses,
    insert_expense,
    get_expense_by_id,
    update_expense,
    delete_expense,
    insert_spending_splits,
    get_expense_splits,
    delete_spending_splits,
    get_expense_participants,
    upsert_room_balance_summary_delta,
)
from app.models.members.members_model import get_member_by_user_id, get_members, get_members_by_user_ids


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


def _resolve_participants(conn: Connection, room_id: int, participant_user_ids: list[int] | None) -> list[dict]:
    if participant_user_ids:
        members = get_members_by_user_ids(conn, room_id, participant_user_ids)
        found_ids = {m["user_id"] for m in members}
        missing = [uid for uid in participant_user_ids if uid not in found_ids]
        if missing:
            raise HTTPException(status_code=400, detail=f"Not room members: {missing}")
        return members
    return get_members(conn, room_id)


def _apply_splits_and_balances(
    conn: Connection, room_id: int, spending_id: int, payer_user_id: int, money: float, participants: list[dict]
) -> None:
    if not participants:
        raise HTTPException(status_code=400, detail="Room has no members to split with")
    amount_owed = round(money / len(participants), 2)
    splits = [
        {
            "user_id": p["user_id"],
            "amount_paid": money if p["user_id"] == payer_user_id else 0,
            "amount_owed": amount_owed,
        }
        for p in participants
    ]
    insert_spending_splits(conn, spending_id, splits)
    for s in splits:
        upsert_room_balance_summary_delta(conn, room_id, s["user_id"], s["amount_paid"] - s["amount_owed"])


def _reverse_splits_and_balances(conn: Connection, room_id: int, spending_id: int) -> list[dict]:
    old_splits = get_expense_splits(conn, spending_id)
    for s in old_splits:
        upsert_room_balance_summary_delta(conn, room_id, s["user_id"], -(s["amount_paid"] - s["amount_owed"]))
    delete_spending_splits(conn, spending_id)
    return old_splits


def add_expense(
    conn: Connection,
    room_id: int,
    material: str,
    money: float,
    current_user: dict,
    created_at=None,
    participant_user_ids: list[int] | None = None,
) -> dict:
    if money <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than 0")
    participants = _resolve_participants(conn, room_id, participant_user_ids)
    expense = insert_expense(conn, room_id, current_user["id"], current_user["email"], material, money, created_at)
    _apply_splits_and_balances(conn, room_id, expense["id"], current_user["id"], money, participants)
    return expense


def add_expense_for_member(
    conn: Connection,
    room_id: int,
    material: str,
    money: float,
    user_id: int,
    created_at=None,
    participant_user_ids: list[int] | None = None,
) -> dict:
    if money <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than 0")
    member = get_member_by_user_id(conn, room_id, user_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    participants = _resolve_participants(conn, room_id, participant_user_ids)
    expense = insert_expense(conn, room_id, user_id, member["email"], material, money, created_at)
    _apply_splits_and_balances(conn, room_id, expense["id"], user_id, money, participants)
    return expense


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

    old_splits = None
    if money is not None:
        old_splits = _reverse_splits_and_balances(conn, room_id, expense_id)

    updated = update_expense(conn, expense_id, material, money, created_at)

    if money is not None:
        participant_ids = [s["user_id"] for s in old_splits]
        participants = get_members_by_user_ids(conn, room_id, participant_ids)
        payer_split = next((s for s in old_splits if s["amount_paid"] > 0), None)
        if payer_split is not None and participants:
            _apply_splits_and_balances(conn, room_id, expense_id, payer_split["user_id"], money, participants)

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

    _reverse_splits_and_balances(conn, room_id, expense_id)
    delete_expense(conn, expense_id)


def get_expense_detail(conn: Connection, room_id: int, expense_id: int) -> dict:
    expense = get_expense_by_id(conn, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    if expense["room"] != room_id:
        raise HTTPException(status_code=404, detail="Expense does not belong to this room")

    participants = [
        {**p, "net": round(p["amount_paid"] - p["amount_owed"], 2)}
        for p in get_expense_participants(conn, expense_id)
    ]
    payer = next((p for p in participants if p["amount_paid"] > 0), None)

    return {
        "id": expense["id"],
        "room": expense["room"],
        "material": expense["material"],
        "money": expense["money"],
        "created_at": expense["created_at"],
        "settled": expense["settled"],
        "settled_at": expense["settled_at"],
        "payer_user_id": payer["user_id"] if payer else None,
        "payer_name": payer["name"] if payer else None,
        "participants": participants,
    }
