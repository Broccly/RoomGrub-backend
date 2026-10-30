from fastapi import HTTPException
from sqlalchemy import Connection
from app.models.expenses.expenses_model import (
    get_expenses,
    get_frequent_items as query_frequent_items,
    insert_expense,
    get_expense_by_id,
    update_expense,
    delete_expense,
    lock_expense,
    insert_spending_splits,
    get_expense_splits,
    delete_spending_splits,
    get_expense_participants,
    upsert_room_balance_summary_delta,
)
from app.models.members.members_model import get_member_by_user_id, get_members, get_members_by_user_ids
from app.services.notifications.push_service import send_push


class ExpenseSettledError(Exception):
    """A settled expense is frozen: changing it would shift balances that were already paid out."""


def list_expenses(
    conn: Connection,
    room_id: int,
    cursor: int | None,
    limit: int,
    settled: bool | None,
    search: str | None,
    user_email: str | None,
    user_id: int | None,
    date_from: str | None,
    date_to: str | None,
) -> dict:
    items = get_expenses(
        conn, room_id, cursor=cursor, limit=limit,
        settled=settled, search=search, user_email=user_email, user_id=user_id,
        date_from=date_from, date_to=date_to,
    )
    next_cursor = items[-1]["id"] if len(items) == limit else None
    return {"items": items, "next_cursor": next_cursor}


def get_frequent_items(conn: Connection, room_id: int, limit: int) -> dict:
    return {"items": query_frequent_items(conn, room_id, limit)}


def _load_participants(
    conn: Connection, room_id: int, payer_id: int, participant_user_ids: list[int]
) -> list[dict]:
    ids = list(dict.fromkeys(participant_user_ids))
    members = get_members_by_user_ids(conn, room_id, ids)
    found = {m["user_id"] for m in members}
    missing = [uid for uid in ids if uid not in found]
    if missing:
        raise ValueError(f"Not room members: {missing}")
    # Only the payer's row records the payment; without it the expense's balances don't add up.
    if payer_id not in found:
        raise ValueError("The payer must be part of the split")
    return members


def _resolve_participants(
    conn: Connection, room_id: int, payer_id: int, participant_user_ids: list[int] | None
) -> list[dict]:
    if participant_user_ids:
        return _load_participants(conn, room_id, payer_id, participant_user_ids)
    return get_members(conn, room_id)


def _apply_splits_and_balances(
    conn: Connection, room_id: int, spending_id: int, payer_user_id: int, money: float, participants: list[dict]
) -> None:
    if not participants:
        raise ValueError("Room has no members to split with")
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


def _reverse_splits_and_balances(conn: Connection, room_id: int, spending_id: int) -> None:
    for s in get_expense_splits(conn, spending_id):
        upsert_room_balance_summary_delta(conn, room_id, s["user_id"], -(s["amount_paid"] - s["amount_owed"]))
    delete_spending_splits(conn, spending_id)


def _notify_expense_added(
    conn: Connection, room_id: int, expense: dict, actor: dict, money: float, participants: list[dict]
) -> None:
    # Only people in the split get notified, never the person who added it.
    recipients = [p["user_id"] for p in participants if p["user_id"] != actor["id"]]
    share = round(money / len(participants), 2)
    send_push(
        conn,
        recipients,
        title=f"{actor['name'] or actor['email']} added {expense['material']}",
        body=f"₹{money:g} · your share ₹{share:g}",
        data={"type": "expense_added", "room_id": str(room_id), "expense_id": str(expense["id"])},
    )


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
        raise ValueError("Amount must be greater than 0")
    participants = _resolve_participants(conn, room_id, current_user["id"], participant_user_ids)
    expense = insert_expense(conn, room_id, current_user["id"], current_user["email"], material, money, created_at)
    _apply_splits_and_balances(conn, room_id, expense["id"], current_user["id"], money, participants)
    _notify_expense_added(conn, room_id, expense, current_user, money, participants)
    return expense


def add_expense_for_member(
    conn: Connection,
    room_id: int,
    material: str,
    money: float,
    user_id: int,
    admin_user: dict,
    created_at=None,
    participant_user_ids: list[int] | None = None,
) -> dict:
    if money <= 0:
        raise ValueError("Amount must be greater than 0")
    member = get_member_by_user_id(conn, room_id, user_id)
    if member is None:
        raise LookupError("Member not found")
    participants = _resolve_participants(conn, room_id, user_id, participant_user_ids)
    expense = insert_expense(conn, room_id, user_id, member["email"], material, money, created_at)
    _apply_splits_and_balances(conn, room_id, expense["id"], user_id, money, participants)
    _notify_expense_added(conn, room_id, expense, admin_user, money, participants)
    return expense


def _get_room_expense(conn: Connection, room_id: int, expense_id: int) -> dict:
    expense = get_expense_by_id(conn, expense_id)
    if not expense:
        raise LookupError("Expense not found")
    if expense["room"] != room_id:
        raise LookupError("Expense does not belong to this room")
    return expense


def _get_changeable_expense(conn: Connection, room_id: int, expense_id: int, membership: dict) -> dict:
    """The expense, if this member may edit or delete it: admins and its payer, while unsettled."""
    # Lock before reading, so the settled check below can't go stale before we commit.
    lock_expense(conn, expense_id)
    expense = _get_room_expense(conn, room_id, expense_id)
    if membership["role"] != "Admin" and expense["user_id"] != membership["user"]["id"]:
        raise PermissionError("Only admins or the person who paid can change this expense")
    if expense["settled"]:
        raise ExpenseSettledError("Settled expenses can't be changed")
    # Editing or deleting reverses the splits, which would move a departed payer's balance.
    if get_member_by_user_id(conn, room_id, expense["user_id"]) is None:
        raise ValueError("The person who paid for this expense has left the room, so it can't be changed")
    return expense


def edit_expense(
    conn: Connection,
    room_id: int,
    expense_id: int,
    material: str | None,
    money: float | None,
    created_at,
    membership: dict,
    participant_user_ids: list[int] | None = None,
) -> dict:
    if money is not None and money <= 0:
        raise ValueError("Amount must be greater than 0")

    expense = _get_changeable_expense(conn, room_id, expense_id, membership)

    if material is None and money is None and created_at is None and participant_user_ids is None:
        raise ValueError("Nothing to update")

    payer_id = expense["user_id"]
    if participant_user_ids is not None:
        participants = _validate_edit_participants(conn, room_id, payer_id, participant_user_ids)
    elif money is not None:
        # Keep the existing split as it is, including anyone in it who has since left.
        participants = [{"user_id": s["user_id"]} for s in get_expense_splits(conn, expense_id)]
        if payer_id not in {p["user_id"] for p in participants}:
            raise ValueError(
                "The payer isn't part of this expense's split. Send participant_user_ids including the payer."
            )
    else:
        participants = None  # only material/created_at changed: splits stay as they are

    if material is not None or money is not None or created_at is not None:
        updated = update_expense(conn, expense_id, material, money, created_at)
        if updated is None:
            raise ExpenseSettledError("Settled expenses can't be changed")
    else:
        updated = expense

    if participants is not None:
        _reverse_splits_and_balances(conn, room_id, expense_id)
        _apply_splits_and_balances(conn, room_id, expense_id, payer_id, updated["money"], participants)

    return updated


def _validate_edit_participants(
    conn: Connection, room_id: int, payer_id: int, participant_user_ids: list[int]
) -> list[dict]:
    if not participant_user_ids:
        raise ValueError("Pick at least one participant")
    return _load_participants(conn, room_id, payer_id, participant_user_ids)


def remove_expense(
    conn: Connection,
    room_id: int,
    expense_id: int,
    membership: dict,
) -> None:
    _get_changeable_expense(conn, room_id, expense_id, membership)

    _reverse_splits_and_balances(conn, room_id, expense_id)
    # Raising rolls back the reversal above with the rest of the transaction.
    if not delete_expense(conn, expense_id):
        raise ExpenseSettledError("Settled expenses can't be changed")


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
