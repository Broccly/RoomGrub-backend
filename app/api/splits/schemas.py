from pydantic import BaseModel, model_validator
from datetime import datetime


class MemberBalance(BaseModel):
    user_id: int
    user_email: str | None
    name: str | None
    profile: str | None
    # None for someone no longer in the room who still has a balance.
    role: str | None
    # Net balance: positive = the room owes them, negative = they owe.
    pending_amount: float
    # What they paid on unsettled expenses, and their share of those expenses.
    unsettled_spent: float
    unsettled_share: float
    # What they paid in this room, settled or not.
    total_spent: float


class UnsettledExpense(BaseModel):
    id: int
    user: str | None
    material: str
    money: float
    created_at: datetime


class SettlementTransaction(BaseModel):
    from_user_id: int
    from_user_email: str | None
    from_name: str | None
    to_user_id: int
    to_user_email: str | None
    to_name: str | None
    amount: float


class SplitsData(BaseModel):
    members: list[MemberBalance]
    # Empty when requested with include_expenses=false.
    unsettled_expenses: list[UnsettledExpense]
    settlements: list[SettlementTransaction]
    # Sum of unsettled expenses in the room.
    total_pending: float
    unsettled_count: int
    # Sum of every expense in the room, settled or not.
    total_spent: float
    last_settled_at: datetime | None


class MemberPendingAmount(BaseModel):
    # Identify the member by user_id; user_email is still accepted from older clients.
    user_id: int | None = None
    user_email: str | None = None
    pending_amount: float

    @model_validator(mode="after")
    def _require_identifier(self) -> "MemberPendingAmount":
        if self.user_id is None and self.user_email is None:
            raise ValueError("Each member needs a user_id or a user_email")
        return self


class SettleAllRequest(BaseModel):
    members: list[MemberPendingAmount]
