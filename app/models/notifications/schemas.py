from datetime import datetime
from pydantic import BaseModel


class NotificationRow(BaseModel):
    id: int
    room_id: int
    activity_type: str
    title: str
    message: str
    created_at: datetime
