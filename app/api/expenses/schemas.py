from pydantic import BaseModel
from datetime import datetime


class ExpenseCreate(BaseModel):
    material: str
    money: float


class ExpenseForMemberCreate(BaseModel):
    material: str
    money: float
    user_email: str


class ExpenseResponse(BaseModel):
    id: int
    room: int
    user: str
    material: str
    money: float
    created_at: datetime
    settled: bool | None


class PaginatedExpenses(BaseModel):
    items: list[ExpenseResponse]
    next_cursor: int | None
