from datetime import datetime
from pydantic import BaseModel


class UnsettledExpenseRow(BaseModel):
    id: int
    user: str | None
    material: str
    money: float
    created_at: datetime


class MemberBalanceRow(BaseModel):
    user_id: int
    user_email: str | None
    name: str | None
    profile: str | None
    role: str | None
    pending_amount: float
    unsettled_spent: float
    unsettled_share: float
    total_spent: float
