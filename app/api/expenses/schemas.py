from pydantic import BaseModel
from datetime import datetime


class ExpenseCreate(BaseModel):
    material: str
    money: float
    created_at: datetime | None = None


class ExpenseForMemberCreate(BaseModel):
    material: str
    money: float
    user_email: str
    created_at: datetime | None = None


class ExpenseResponse(BaseModel):
    id: int
    room: int
    user: str
    material: str
    money: float
    created_at: datetime
    settled: bool | None
    user_name: str | None
    user_profile: str | None
    settled_at: datetime | None


class ExpenseUpdate(BaseModel):
    material: str | None = None
    money: float | None = None
    created_at: datetime | None = None


class PaginatedExpenses(BaseModel):
    items: list[ExpenseResponse]
    next_cursor: int | None
