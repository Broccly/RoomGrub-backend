from pydantic import BaseModel
from datetime import datetime


class NotificationCreate(BaseModel):
    room_id: int
    activity_type: str
    title: str
    message: str
    data: dict | None = None


class NotificationResponse(BaseModel):
    id: int
    room_id: int
    activity_type: str
    title: str
    message: str
    created_at: datetime


class PushSubscriptionUpsert(BaseModel):
    endpoint: str
    p256dh_key: str
    auth_key: str
