import redis
from fastapi import Depends, HTTPException
from sqlalchemy import Connection, text
from db.engine import db_conn
from db.redis_client import redis_conn
from app.dependencies.current_user import get_current_user
from app.cache.auth_cache import get_cached_room_access, set_cached_room_access


def require_room_member(
    room_id: int,
    current_user: dict = Depends(get_current_user),
    conn: Connection = Depends(db_conn),
    redis_client: redis.Redis = Depends(redis_conn),
) -> dict:
    cached = get_cached_room_access(redis_client, current_user["id"], room_id)
    if cached is not None:
        return {"id": cached["id"], "role": cached["role"], "user": current_user}

    row = conn.execute(
        text(
            'SELECT id, role FROM "UserRooms" '
            "WHERE room_id = :room_id AND user_id = :user_id"
        ),
        {"room_id": room_id, "user_id": current_user["id"]},
    ).fetchone()

    if not row:
        raise HTTPException(status_code=403, detail="Not a member of this room")

    membership = {"id": row.id, "role": row.role}
    set_cached_room_access(redis_client, current_user["id"], room_id, membership)
    return {**membership, "user": current_user}


def require_room_admin(
    membership: dict = Depends(require_room_member),
) -> dict:
    if membership["role"] != "Admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return membership


def require_room_non_admin(
    membership: dict = Depends(require_room_member),
) -> dict:
    if membership["role"] == "Admin":
        raise HTTPException(status_code=403, detail="Admins cannot perform this action")
    return membership
