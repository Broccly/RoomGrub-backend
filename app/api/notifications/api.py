from fastapi import APIRouter, Depends, status
from sqlalchemy import Connection
from db.engine import db_conn
from app.dependencies.room_access import require_room_member
from app.api.notifications.schemas import (
    NotificationCreate,
    NotificationResponse,
    PushSubscriptionUpsert,
)
from app.services.notifications import notifications_services

router = APIRouter(prefix="/api/v1/rooms", tags=["Notifications"])


@router.post("/{room_id}/notifications", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
def create_notification(
    room_id: int,
    body: NotificationCreate,
    conn: Connection = Depends(db_conn),
    membership: dict = Depends(require_room_member),
) -> NotificationResponse:
    return notifications_services.create_notification(
        conn,
        room_id=room_id,
        current_user=membership["user"],
        activity_type=body.activity_type,
        title=body.title,
        message=body.message,
        data=body.data,
    )


@router.get(
    "/{room_id}/notifications",
    response_model=list[NotificationResponse],
)
def list_notifications(
    room_id: int,
    conn: Connection = Depends(db_conn),
    membership: dict = Depends(require_room_member),
) -> list[NotificationResponse]:
    return notifications_services.list_notifications(conn, room_id)


@router.post(
    "/{room_id}/push-subscriptions",
    status_code=status.HTTP_204_NO_CONTENT,
)
def register_push(
    room_id: int,
    body: PushSubscriptionUpsert,
    conn: Connection = Depends(db_conn),
    membership: dict = Depends(require_room_member),
) -> None:
    notifications_services.register_push(
        conn, room_id, membership["user"]["id"], body.endpoint, body.p256dh_key, body.auth_key
    )


@router.delete(
    "/{room_id}/push-subscriptions",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unregister_push(
    room_id: int,
    conn: Connection = Depends(db_conn),
    membership: dict = Depends(require_room_member),
) -> None:
    notifications_services.unregister_push(conn, room_id, membership["user"]["id"])
