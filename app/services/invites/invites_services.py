import redis
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from sqlalchemy import Connection
from app.models.invites.invites_model import (
    insert_invite,
    get_invite_by_token,
    update_invite_status,
    check_membership,
    insert_member,
)
from app.cache.auth_cache import invalidate_cached_room_access

INVITE_EXPIRY_DAYS = 7


def create_invite(conn: Connection, room_id: int, current_user: dict) -> dict:
    token = insert_invite(conn, room_id, current_user["id"])
    return {
        "token": token,
        "room_id": room_id,
        "invited_by_email": current_user["email"],
        "invited_by_name": current_user.get("name") or current_user["email"],
        "invited_by_profile": current_user.get("profile"),
        "days_left": INVITE_EXPIRY_DAYS,
    }


def validate_invite(conn: Connection, token: str) -> dict:
    invite = get_invite_by_token(conn, token)
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite["status"] != "pending":
        raise HTTPException(status_code=410, detail=f"Invite is {invite['status']}")

    created_at = invite["created_at"]
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    expiry = created_at + timedelta(days=INVITE_EXPIRY_DAYS)
    now = datetime.now(timezone.utc)
    if now > expiry:
        update_invite_status(conn, token, "expired")
        raise HTTPException(status_code=410, detail="Invite has expired")

    days_left = max(0, (expiry - now).days)
    return {
        "token": invite["token"],
        "room_id": invite["room_id"],
        "invited_by_email": invite["invited_by_email"],
        "invited_by_name": invite["invited_by_name"] or invite["invited_by_email"],
        "invited_by_profile": invite["invited_by_profile"],
        "days_left": days_left,
    }


def accept_invite(conn: Connection, token: str, current_user: dict, redis_client: redis.Redis) -> dict:
    invite = validate_invite(conn, token)
    room_id = invite["room_id"]

    if check_membership(conn, current_user["id"], room_id):
        return {"room_id": room_id, "message": "Already a member"}

    insert_member(conn, current_user["id"], room_id)
    update_invite_status(conn, token, "accepted")
    invalidate_cached_room_access(redis_client, current_user["id"], room_id)
    return {"room_id": room_id, "message": "Joined room successfully"}


def reject_invite(conn: Connection, token: str) -> None:
    invite = get_invite_by_token(conn, token)
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    update_invite_status(conn, token, "rejected")
