from pydantic import BaseModel
from datetime import datetime


class MemberBalance(BaseModel):
    user_email: str
    name: str | None
    profile: str | None
    pending_amount: float


class UnsettledExpense(BaseModel):
    id: int
    user: str
    material: str
    money: float
    created_at: datetime


class SettlementTransaction(BaseModel):
    from_user_email: str
    from_name: str | None
    to_user_email: str
    to_name: str | None
    amount: float


class SplitsData(BaseModel):
    members: list[MemberBalance]
    unsettled_expenses: list[UnsettledExpense]
    settlements: list[SettlementTransaction]


class MemberPendingAmount(BaseModel):
    user_email: str
    pending_amount: float


class SettleAllRequest(BaseModel):
    members: list[MemberPendingAmount]
