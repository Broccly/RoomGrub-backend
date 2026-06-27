from fastapi import HTTPException
from sqlalchemy import Connection
from app.models.splits.splits_model import (
    get_unsettled_expenses,
    get_member_balances,
    get_pending_for_user,
    settle_user_expenses,
)

TOLERANCE = 0.01


def get_splits_data(conn: Connection, room_id: int) -> dict:
    members = get_member_balances(conn, room_id)
    unsettled = get_unsettled_expenses(conn, room_id)
    return {"members": members, "unsettled_expenses": unsettled}


def settle_one(conn: Connection, room_id: int, user_email: str, client_pending: float) -> None:
    server_pending = get_pending_for_user(conn, room_id, user_email)
    if abs(server_pending - client_pending) > TOLERANCE:
        raise HTTPException(
            status_code=400,
            detail=f"Pending amount mismatch for {user_email}: "
                   f"server={server_pending:.2f}, client={client_pending:.2f}",
        )
    if server_pending <= 0:
        raise HTTPException(status_code=400, detail=f"No pending amount for {user_email}")
    settle_user_expenses(conn, room_id, user_email)


def settle_all(conn: Connection, room_id: int, members: list[dict]) -> None:
    for member in members:
        server_pending = get_pending_for_user(conn, room_id, member["user_email"])
        if abs(server_pending - member["pending_amount"]) > TOLERANCE:
            raise HTTPException(
                status_code=400,
                detail=f"Pending amount mismatch for {member['user_email']}: "
                       f"server={server_pending:.2f}, client={member['pending_amount']:.2f}",
            )

    for member in members:
        server_pending = get_pending_for_user(conn, room_id, member["user_email"])
        if server_pending > 0:
            settle_user_expenses(conn, room_id, member["user_email"])
