from pydantic import BaseModel
from datetime import datetime


class MemberBalance(BaseModel):
    user_email: str
    name: str | None
    pending_amount: float


class UnsettledExpense(BaseModel):
    id: int
    user: str
    material: str
    money: float
    created_at: datetime


class SplitsData(BaseModel):
    members: list[MemberBalance]
    unsettled_expenses: list[UnsettledExpense]


class SettleRequest(BaseModel):
    user_email: str
    pending_amount: float


class SettleAllRequest(BaseModel):
    members: list[SettleRequest]
