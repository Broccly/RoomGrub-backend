from pydantic import BaseModel


class InsertRoomResponse(BaseModel):
    id: int


class ListRoomsResponse(BaseModel):
    id: int
    members: int
    admin: str | None


class MemberStatRow(BaseModel):
    user_id: int
    email: str
    name: str | None
    profile: str | None
    role: str
    total_spent: float
    pending_amount: float