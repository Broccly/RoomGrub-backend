from pydantic import BaseModel


class InviteResponse(BaseModel):
    token: str
    room_id: int
    invited_by_email: str
    invited_by_name: str
    days_left: int


class InviteAcceptResponse(BaseModel):
    room_id: int
    message: str
