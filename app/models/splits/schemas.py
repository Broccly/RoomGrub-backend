from datetime import datetime
from pydantic import BaseModel


class UnsettledExpenseRow(BaseModel):
    id: int
    user: str
    material: str
    money: float
    created_at: datetime


class MemberBalanceRow(BaseModel):
    user_email: str
    name: str | None
    profile: str | None
    pending_amount: float
