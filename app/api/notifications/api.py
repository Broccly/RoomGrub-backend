from fastapi import APIRouter, Depends, status
from sqlalchemy import Connection
from db.engine import db_conn
from app.dependencies.current_user import get_current_user
from app.api.notifications.schemas import (
    NotificationCreate,
    NotificationResponse,
    PushSubscriptionUpsert,
)
from app.services.notifications import notifications_services

router = APIRouter(tags=["Notifications"])


@router.post("/api/v1/notifications", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
def create_notification(
    body: NotificationCreate,
    conn: Connection = Depends(db_conn),
    current_user: dict = Depends(get_current_user),
) -> NotificationResponse:
    return notifications_services.create_notification(
        conn,
        room_id=body.room_id,
        current_user=current_user,
        activity_type=body.activity_type,
        title=body.title,
        message=body.message,
        data=body.data,
    )


@router.get(
    "/api/v1/rooms/{room_id}/notifications",
    response_model=list[NotificationResponse],
)
def list_notifications(
    room_id: int,
    conn: Connection = Depends(db_conn),
    current_user: dict = Depends(get_current_user),
) -> list[NotificationResponse]:
    return notifications_services.list_notifications(conn, room_id)


@router.post(
    "/api/v1/rooms/{room_id}/push-subscriptions",
    status_code=status.HTTP_204_NO_CONTENT,
)
def register_push(
    room_id: int,
    body: PushSubscriptionUpsert,
    conn: Connection = Depends(db_conn),
    current_user: dict = Depends(get_current_user),
) -> None:
    notifications_services.register_push(
        conn, room_id, current_user["id"], body.endpoint, body.p256dh_key, body.auth_key
    )


@router.delete(
    "/api/v1/rooms/{room_id}/push-subscriptions",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unregister_push(
    room_id: int,
    conn: Connection = Depends(db_conn),
    current_user: dict = Depends(get_current_user),
) -> None:
    notifications_services.unregister_push(conn, room_id, current_user["id"])
