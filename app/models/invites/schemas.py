from datetime import datetime
from pydantic import BaseModel


class InviteByTokenRow(BaseModel):
    token: str
    room_id: int
    room_name: str | None
    status: str
    created_at: datetime
    invited_by_email: str | None
    invited_by_name: str | None
    invited_by_profile: str | None
