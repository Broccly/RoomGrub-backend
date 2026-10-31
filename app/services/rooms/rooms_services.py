import redis
from fastapi import HTTPException
from sqlalchemy import Connection
from app.models.rooms.rooms_model import (
    insert_room,
    insert_user_room,
    update_room_name,
    get_rooms_for_user,
    get_member_previews,
    get_room_by_id,
    get_total_spent,
    get_pending_amount,
    get_member_stats,
    count_unsettled_expenses,
    delete_room_cascade,
)
from app.models.members.members_model import get_members
from app.cache.auth_cache import invalidate_all_room_access_for_room


def create_room(conn: Connection, current_user: dict, name: str | None = None) -> dict:
    room = insert_room(conn, name)
    insert_user_room(conn, user_id=current_user["id"], room_id=room["id"], role="Admin")
    return {
        **room,
        "members": 1,
        "admin": current_user["email"],
        "admin_user_id": current_user["id"],
        "admin_name": current_user["name"],
    }


def rename_room(conn: Connection, room_id: int, name: str) -> dict:
    if not update_room_name(conn, room_id, name):
        raise LookupError("Room not found")
    return get_room_by_id(conn, room_id)


def list_rooms(conn: Connection, current_user: dict) -> list[dict]:
    rooms = get_rooms_for_user(conn, current_user["id"])
    previews: dict[int, list[dict]] = {}
    for p in get_member_previews(conn, [r["id"] for r in rooms]):
        previews.setdefault(p.pop("room_id"), []).append(p)
    return [{**r, "member_preview": previews.get(r["id"], [])} for r in rooms]


def get_room_summary(conn: Connection, room_id: int) -> dict:
    room = get_room_by_id(conn, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    total_spent = get_total_spent(conn, room_id)
    pending = get_pending_amount(conn, room_id)
    return {**room, "total_spent": total_spent, "pending_amount": pending}


def get_room_dashboard(conn: Connection, room_id: int) -> dict:
    room = get_room_by_id(conn, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    members = get_member_stats(conn, room_id)
    return {"room": room, "members": members}


def delete_room(conn: Connection, room_id: int, redis_client: redis.Redis) -> None:
    room = get_room_by_id(conn, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    unsettled = count_unsettled_expenses(conn, room_id)
    if unsettled > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete room: {unsettled} unsettled expense(s) remain",
        )
    member_user_ids = [member["user_id"] for member in get_members(conn, room_id)]
    delete_room_cascade(conn, room_id)
    invalidate_all_room_access_for_room(redis_client, room_id, member_user_ids)
