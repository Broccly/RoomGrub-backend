from datetime import datetime
from pydantic import BaseModel


class ExpenseRow(BaseModel):
    id: int
    room: int
    user_id: int
    # Payer's email; None when the payer has none.
    user: str | None
    material: str
    money: float
    created_at: datetime
    settled: bool | None
    user_name: str | None
    user_profile: str | None
    settled_at: datetime | None


class FrequentItemRow(BaseModel):
    label: str
