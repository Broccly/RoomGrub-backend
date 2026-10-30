import redis
from fastapi import HTTPException
from sqlalchemy import Connection
from app.models.members.members_model import (
    get_members,
    get_member_by_user_id,
    get_member_pending_expenses,
    get_member_pending,
    get_member_total_spent,
    update_member_role,
    remove_user_room,
    get_my_membership,
    has_unsettled_splits,
)
from app.cache.auth_cache import invalidate_cached_room_access


def list_members(conn: Connection, room_id: int) -> list[dict]:
    return get_members(conn, room_id)


def get_member_detail(conn: Connection, room_id: int, user_id: int) -> dict:
    member = get_member_by_user_id(conn, room_id, user_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    expenses = get_member_pending_expenses(conn, room_id, user_id)
    total_spent = get_member_total_spent(conn, room_id, user_id)
    pending = get_member_pending(conn, room_id, user_id)
    return {**member, "total_spent": total_spent, "pending_amount": pending, "expenses": expenses}


def change_member_role(
    conn: Connection, room_id: int, user_id: int, new_role: str, current_user: dict, redis_client: redis.Redis
) -> None:
    if new_role not in ("Admin", "Member"):
        raise HTTPException(status_code=400, detail="Role must be 'Admin' or 'Member'")
    member = get_member_by_user_id(conn, room_id, user_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if user_id == current_user["id"] and new_role == "Member":
        raise HTTPException(status_code=400, detail="Admin cannot demote themselves")
    update_member_role(conn, room_id, user_id, new_role)
    invalidate_cached_room_access(redis_client, user_id, room_id)


def remove_member(
    conn: Connection, room_id: int, user_id: int, current_user: dict, redis_client: redis.Redis
) -> None:
    member = get_member_by_user_id(conn, room_id, user_id)
    if not member:
        raise LookupError("Member not found")
    if user_id == current_user["id"]:
        raise ValueError("Admin cannot remove themselves. Use /members/me to exit.")
    # Unsettled expenses can still be edited or deleted, which would move a departed member's balance.
    # Also covers a non-zero balance: a balance only moves through unsettled expenses.
    if has_unsettled_splits(conn, room_id, user_id):
        raise ValueError("This member is part of unsettled expenses. Settle the room before removing them.")
    remove_user_room(conn, room_id, user_id)
    invalidate_cached_room_access(redis_client, user_id, room_id)


def exit_room(conn: Connection, room_id: int, current_user: dict, redis_client: redis.Redis) -> None:
    membership = get_my_membership(conn, room_id, current_user["id"])
    if not membership:
        raise PermissionError("Not a member of this room")
    if membership["role"] == "Admin":
        raise ValueError("Admin cannot exit the room. Transfer admin role first.")
    if has_unsettled_splits(conn, room_id, current_user["id"]):
        raise ValueError("You're part of unsettled expenses. Ask the admin to settle the room before leaving.")
    remove_user_room(conn, room_id, current_user["id"])
    invalidate_cached_room_access(redis_client, current_user["id"], room_id)
