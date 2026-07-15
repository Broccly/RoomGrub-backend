from datetime import datetime
from pydantic import BaseModel


class InsertRoomResponse(BaseModel):
    id: int


class ListRoomsResponse(BaseModel):
    id: int
    members: int
    admin: str | None


class RecentExpenseRow(BaseModel):
    id: int
    material: str
    money: float
    user: str
    created_at: datetime


class MemberStatRow(BaseModel):
    user_id: int
    email: str
    name: str | None
    role: str
    total_spent: float
    pending_amount: float