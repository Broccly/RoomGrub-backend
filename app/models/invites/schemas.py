from datetime import datetime
from pydantic import BaseModel


class InviteByTokenRow(BaseModel):
    token: str
    room_id: int
    status: str
    created_at: datetime
    invited_by_email: str
    invited_by_name: str | None
    invited_by_profile: str | None
