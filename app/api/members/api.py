from fastapi import APIRouter, Depends, status
from sqlalchemy import Connection
from db.engine import db_conn
from app.dependencies.room_access import require_room_admin, require_room_member, require_room_non_admin
from app.api.members.schemas import (
    MemberResponse,
    MemberDetail,
    RoleUpdate,
    ContributeRequest,
)
from app.services.members import members_services

router = APIRouter(prefix="/api/v1/rooms", tags=["Members"])


@router.get("/{room_id}/members", response_model=list[MemberResponse])
def list_members(
    room_id: int,
    conn: Connection = Depends(db_conn),
    membership: dict = Depends(require_room_member),
) -> list[MemberResponse]:
    return members_services.list_members(conn, room_id)


@router.get("/{room_id}/members/{user_id}", response_model=MemberDetail)
def get_member_detail(
    room_id: int,
    user_id: int,
    conn: Connection = Depends(db_conn),
    membership: dict = Depends(require_room_member),
) -> MemberDetail:
    return members_services.get_member_detail(conn, room_id, user_id)


@router.patch("/{room_id}/members/{user_id}/role", status_code=status.HTTP_204_NO_CONTENT)
def update_member_role(
    room_id: int,
    user_id: int,
    body: RoleUpdate,
    conn: Connection = Depends(db_conn),
    membership: dict = Depends(require_room_admin),
) -> None:
    members_services.change_member_role(conn, room_id, user_id, body.role, membership["user"])


@router.delete("/{room_id}/members/me", status_code=status.HTTP_204_NO_CONTENT)
def exit_room(
    room_id: int,
    conn: Connection = Depends(db_conn),
    membership: dict = Depends(require_room_non_admin),
) -> None:
    members_services.exit_room(conn, room_id, membership["user"])


@router.delete("/{room_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    room_id: int,
    user_id: int,
    conn: Connection = Depends(db_conn),
    membership: dict = Depends(require_room_admin),
) -> None:
    members_services.remove_member(conn, room_id, user_id, membership["user"])


@router.post("/{room_id}/members/{user_id}/settle", status_code=status.HTTP_204_NO_CONTENT)
def settle_member(
    room_id: int,
    user_id: int,
    conn: Connection = Depends(db_conn),
    membership: dict = Depends(require_room_admin),
) -> None:
    members_services.settle_member(conn, room_id, user_id)


@router.post("/{room_id}/members/{user_id}/contribute", status_code=status.HTTP_204_NO_CONTENT)
def contribute(
    room_id: int,
    user_id: int,
    body: ContributeRequest,
    conn: Connection = Depends(db_conn),
    membership: dict = Depends(require_room_admin),
) -> None:
    members_services.record_contribution(conn, room_id, user_id, body.amount)
