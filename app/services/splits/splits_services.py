from fastapi import HTTPException
from sqlalchemy import Connection
from app.models.splits.splits_model import (
    get_unsettled_expenses,
    get_member_balances,
    get_pending_for_user,
    settle_all_room,
)

TOLERANCE = 0.01


def _simplify_debts(balances: list[dict]) -> list[dict]:
    creditors = sorted(
        (dict(b) for b in balances if b["pending_amount"] > TOLERANCE),
        key=lambda b: -b["pending_amount"],
    )
    debtors = sorted(
        (dict(b) for b in balances if b["pending_amount"] < -TOLERANCE),
        key=lambda b: b["pending_amount"],
    )

    transactions = []
    i, j = 0, 0
    while i < len(debtors) and j < len(creditors):
        debtor = debtors[i]
        creditor = creditors[j]
        amount = round(min(-debtor["pending_amount"], creditor["pending_amount"]), 2)
        if amount > TOLERANCE:
            transactions.append({
                "from_user_email": debtor["user_email"],
                "from_name": debtor["name"],
                "to_user_email": creditor["user_email"],
                "to_name": creditor["name"],
                "amount": amount,
            })
        debtor["pending_amount"] = round(debtor["pending_amount"] + amount, 2)
        creditor["pending_amount"] = round(creditor["pending_amount"] - amount, 2)
        if abs(debtor["pending_amount"]) <= TOLERANCE:
            i += 1
        if abs(creditor["pending_amount"]) <= TOLERANCE:
            j += 1
    return transactions


def get_splits_data(conn: Connection, room_id: int) -> dict:
    members = get_member_balances(conn, room_id)
    unsettled = get_unsettled_expenses(conn, room_id)
    settlements = _simplify_debts(members)
    return {"members": members, "unsettled_expenses": unsettled, "settlements": settlements}


def settle_all(conn: Connection, room_id: int, members: list[dict]) -> None:
    for member in members:
        server_pending = get_pending_for_user(conn, room_id, member["user_email"])
        if abs(server_pending - member["pending_amount"]) > TOLERANCE:
            raise HTTPException(
                status_code=400,
                detail=f"Pending amount mismatch for {member['user_email']}: "
                       f"server={server_pending:.2f}, client={member['pending_amount']:.2f}",
            )

    settle_all_room(conn, room_id)
