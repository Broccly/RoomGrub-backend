from fastapi import HTTPException
from sqlalchemy import Connection
from app.models.members.members_model import (
    get_members,
    get_member_by_user_id,
    get_member_pending_expenses,
    get_member_pending,
    update_member_role,
    remove_user_room,
    get_my_membership,
    insert_balance_debit,
    insert_balance_credit,
)


def list_members(conn: Connection, room_id: int) -> list[dict]:
    return get_members(conn, room_id)


def get_member_detail(conn: Connection, room_id: int, user_id: int) -> dict:
    member = get_member_by_user_id(conn, room_id, user_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    expenses = get_member_pending_expenses(conn, room_id, member["email"])
    total_spent = sum(e["money"] for e in expenses)
    pending = get_member_pending(conn, room_id, member["email"])
    return {**member, "total_spent": total_spent, "pending_amount": pending, "expenses": expenses}


def change_member_role(
    conn: Connection, room_id: int, user_id: int, new_role: str, current_user: dict
) -> None:
    if new_role not in ("Admin", "Member"):
        raise HTTPException(status_code=400, detail="Role must be 'Admin' or 'Member'")
    member = get_member_by_user_id(conn, room_id, user_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if user_id == current_user["id"] and new_role == "Member":
        raise HTTPException(status_code=400, detail="Admin cannot demote themselves")
    update_member_role(conn, room_id, user_id, new_role)


def remove_member(
    conn: Connection, room_id: int, user_id: int, current_user: dict
) -> None:
    member = get_member_by_user_id(conn, room_id, user_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if user_id == current_user["id"]:
        raise HTTPException(
            status_code=400, detail="Admin cannot remove themselves. Use /members/me to exit."
        )
    remove_user_room(conn, room_id, user_id)


def exit_room(conn: Connection, room_id: int, current_user: dict) -> None:
    membership = get_my_membership(conn, room_id, current_user["id"])
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this room")
    if membership["role"] == "Admin":
        raise HTTPException(
            status_code=400, detail="Admin cannot exit the room. Transfer admin role first."
        )
    remove_user_room(conn, room_id, current_user["id"])


def settle_member(conn: Connection, room_id: int, user_id: int) -> None:
    member = get_member_by_user_id(conn, room_id, user_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    pending = get_member_pending(conn, room_id, member["email"])
    if pending <= 0:
        raise HTTPException(status_code=400, detail="No pending amount to settle")
    insert_balance_debit(conn, room_id, member["email"], pending)


def record_contribution(conn: Connection, room_id: int, user_id: int, amount: float) -> None:
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than 0")
    member = get_member_by_user_id(conn, room_id, user_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    insert_balance_credit(conn, room_id, member["email"], amount)
