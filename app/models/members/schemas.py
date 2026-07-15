from datetime import datetime
from pydantic import BaseModel


class MemberRow(BaseModel):
    id: int
    user_id: int
    email: str
    name: str | None
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
    email: str
    role: str
