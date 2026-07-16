import redis
from fastapi import APIRouter, Depends, status
from sqlalchemy import Connection
from db.engine import db_conn
from db.redis_client import redis_conn
from app.dependencies.current_user import get_current_user
from app.dependencies.room_access import require_room_admin
from app.api.invites.schemas import InviteResponse, InviteAcceptResponse
from app.services.invites import invites_services

router = APIRouter(tags=["Invites"])


@router.post(
    "/api/v1/rooms/{room_id}/invites",
    response_model=InviteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_invite(
    room_id: int,
    conn: Connection = Depends(db_conn),
    membership: dict = Depends(require_room_admin),
) -> InviteResponse:
    return invites_services.create_invite(conn, room_id, membership["user"])


@router.get("/api/v1/invites/{token}", response_model=InviteResponse)
def validate_invite(
    token: str,
    conn: Connection = Depends(db_conn),
) -> InviteResponse:
    return invites_services.validate_invite(conn, token)


@router.post("/api/v1/invites/{token}/accept", response_model=InviteAcceptResponse)
def accept_invite(
    token: str,
    conn: Connection = Depends(db_conn),
    current_user: dict = Depends(get_current_user),
    redis_client: redis.Redis = Depends(redis_conn),
) -> InviteAcceptResponse:
    return invites_services.accept_invite(conn, token, current_user, redis_client)


@router.post("/api/v1/invites/{token}/reject", status_code=status.HTTP_204_NO_CONTENT)
def reject_invite(
    token: str,
    conn: Connection = Depends(db_conn),
    current_user: dict = Depends(get_current_user),
) -> None:
    invites_services.reject_invite(conn, token)
