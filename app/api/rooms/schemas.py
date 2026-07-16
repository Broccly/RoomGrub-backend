from pydantic import BaseModel
from datetime import datetime


class RoomResponse(BaseModel):
    id: int
    members: int
    admin: str


class ExpenseSummary(BaseModel):
    id: int
    material: str
    money: float
    user: str
    created_at: datetime
    user_name: str | None
    user_profile: str | None
    settled_at: datetime | None


class RoomSummary(RoomResponse):
    total_spent: float
    pending_amount: float
    recent_expenses: list[ExpenseSummary]


class MemberStat(BaseModel):
    user_id: int
    email: str
    name: str | None
    profile: str | None
    role: str
    total_spent: float
    pending_amount: float


class DashboardResponse(BaseModel):
    room: RoomResponse
    members: list[MemberStat]
