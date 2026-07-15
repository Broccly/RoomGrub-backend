from datetime import datetime
from pydantic import BaseModel


class ExpenseRow(BaseModel):
    id: int
    room: int
    user: str
    material: str
    money: float
    created_at: datetime
    settled: bool | None
