from fastapi import HTTPException
from sqlalchemy import Connection
from app.models.rooms.rooms_model import (
    insert_room,
    insert_user_room,
    get_rooms_for_user,
    get_room_by_id,
    get_total_spent,
    get_pending_amount,
    get_recent_expenses,
    get_member_stats,
    count_unsettled_expenses,
    delete_room_cascade,
)


def create_room(conn: Connection, budget: float | None, current_user: dict) -> dict:
    room = insert_room(conn, admin_email=current_user["email"], budget=budget)
    insert_user_room(conn, user_id=current_user["id"], room_id=room["id"], role="Admin")
    return room


def list_rooms(conn: Connection, current_user: dict) -> list[dict]:
    return get_rooms_for_user(conn, current_user["id"])


def get_room_summary(conn: Connection, room_id: int) -> dict:
    room = get_room_by_id(conn, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    total_spent = get_total_spent(conn, room_id)
    pending = get_pending_amount(conn, room_id)
    recent = get_recent_expenses(conn, room_id, limit=5)
    return {**room, "total_spent": total_spent, "pending_amount": pending, "recent_expenses": recent}


def get_room_dashboard(conn: Connection, room_id: int) -> dict:
    room = get_room_by_id(conn, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    members = get_member_stats(conn, room_id)
    return {"room": room, "members": members}


def delete_room(conn: Connection, room_id: int, current_user: dict) -> None:
    room = get_room_by_id(conn, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room["admin"] != current_user["email"]:
        raise HTTPException(status_code=403, detail="Only the room admin can delete this room")
    unsettled = count_unsettled_expenses(conn, room_id)
    if unsettled > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete room: {unsettled} unsettled expense(s) remain",
        )
    delete_room_cascade(conn, room_id)
