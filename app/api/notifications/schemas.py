from pydantic import BaseModel
from datetime import datetime


class NotificationCreate(BaseModel):
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


class FcmTokenRegister(BaseModel):
    fcm_token: str
    platform: str = "android"


class FcmTokenUnregister(BaseModel):
    fcm_token: str
