from fastapi import Depends, HTTPException
from sqlalchemy import Connection, text
from db.engine import db_conn
from app.dependencies.current_user import get_current_user


def require_room_member(
    room_id: int,
    current_user: dict = Depends(get_current_user),
    conn: Connection = Depends(db_conn),
) -> dict:
    row = conn.execute(
        text(
            'SELECT id, role FROM "UserRooms" '
            "WHERE room_id = :room_id AND user_id = :user_id"
        ),
        {"room_id": room_id, "user_id": current_user["id"]},
    ).fetchone()

    if not row:
        raise HTTPException(status_code=403, detail="Not a member of this room")

    return {"id": row.id, "role": row.role, "user": current_user}


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
