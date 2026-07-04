from fastapi import HTTPException
from sqlalchemy import Connection
from app.models.splits.splits_model import (
    get_unsettled_expenses,
    get_member_balances,
    get_pending_for_user,
    settle_member_balance,
    settle_all_room,
    get_filtered_unsettled_expenses,
    get_pending_for_user_filtered,
    settle_filtered_room,
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
    if abs(server_pending) <= TOLERANCE:
        raise HTTPException(status_code=400, detail=f"No pending amount for {user_email}")
    settle_member_balance(conn, room_id, user_email, server_pending)


def settle_all(
    conn: Connection,
    room_id: int,
    members: list[dict],
    date_from=None,
    date_to=None,
    member_emails: list[str] | None = None,
) -> None:
    if date_from is None and date_to is None and not member_emails:
        for member in members:
            server_pending = get_pending_for_user(conn, room_id, member["user_email"])
            if abs(server_pending - member["pending_amount"]) > TOLERANCE:
                raise HTTPException(
                    status_code=400,
                    detail=f"Pending amount mismatch for {member['user_email']}: "
                           f"server={server_pending:.2f}, client={member['pending_amount']:.2f}",
                )

        settle_all_room(conn, room_id)
        return

    settle_filtered(conn, room_id, members, date_from, date_to, member_emails)


def settle_filtered(
    conn: Connection,
    room_id: int,
    members: list[dict],
    date_from=None,
    date_to=None,
    member_emails: list[str] | None = None,
) -> None:
    for member in members:
        server_pending = get_pending_for_user_filtered(
            conn, room_id, member["user_email"], date_from, date_to, member_emails
        )
        if abs(server_pending - member["pending_amount"]) > TOLERANCE:
            raise HTTPException(
                status_code=400,
                detail=f"Pending amount mismatch for {member['user_email']}: "
                       f"server={server_pending:.2f}, client={member['pending_amount']:.2f}",
            )

    expenses = get_filtered_unsettled_expenses(conn, room_id, date_from, date_to, member_emails)
    settle_filtered_room(conn, room_id, [e["id"] for e in expenses])
