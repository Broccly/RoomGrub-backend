from pydantic import BaseModel
from datetime import datetime


class RoomCreate(BaseModel):
    budget: float | None = None


class RoomResponse(BaseModel):
    id: int
    members: int
    budget: float | None
    admin: str


class ExpenseSummary(BaseModel):
    id: int
    material: str
    money: float
    user: str
    created_at: datetime


class RoomSummary(RoomResponse):
    total_spent: float
    pending_amount: float
    recent_expenses: list[ExpenseSummary]


class MemberStat(BaseModel):
    user_id: int
    email: str
    name: str | None
    role: str
    total_spent: float
    pending_amount: float


class DashboardResponse(BaseModel):
    room: RoomResponse
    members: list[MemberStat]
