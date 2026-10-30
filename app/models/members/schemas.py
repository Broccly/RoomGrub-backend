from datetime import datetime
from pydantic import BaseModel


class MemberRow(BaseModel):
    id: int
    user_id: int
    email: str | None
    name: str | None
    profile: str | None
    role: str
    joined_at: datetime


class MemberPendingExpenseRow(BaseModel):
    id: int
    material: str
    money: float
    created_at: datetime
    settled: bool | None


class MyMembershipRow(BaseModel):
    id: int
    email: str | None
    role: str
