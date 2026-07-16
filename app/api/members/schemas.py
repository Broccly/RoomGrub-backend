from pydantic import BaseModel
from datetime import datetime


class MemberResponse(BaseModel):
    id: int
    user_id: int
    email: str
    name: str | None
    profile: str | None
    role: str
    joined_at: datetime


class ExpenseSummary(BaseModel):
    id: int
    material: str
    money: float
    created_at: datetime
    settled: bool | None


class MemberDetail(MemberResponse):
    total_spent: float
    pending_amount: float
    expenses: list[ExpenseSummary]


class RoleUpdate(BaseModel):
    role: str


class SettleRequest(BaseModel):
    pass


class ContributeRequest(BaseModel):
    amount: float
