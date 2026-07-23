from pydantic import BaseModel
from datetime import datetime


class ExpenseCreate(BaseModel):
    material: str
    money: float
    created_at: datetime | None = None
    participant_user_ids: list[int] | None = None


class ExpenseForMemberCreate(BaseModel):
    material: str
    money: float
    user_id: int
    created_at: datetime | None = None
    participant_user_ids: list[int] | None = None


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


class ExpenseParticipant(BaseModel):
    user_id: int
    name: str | None
    profile: str | None
    amount_paid: float
    amount_owed: float
    net: float


class ExpenseDetail(BaseModel):
    id: int
    room: int
    material: str
    money: float
    created_at: datetime
    settled: bool | None
    settled_at: datetime | None
    payer_user_id: int | None
    payer_name: str | None
    participants: list[ExpenseParticipant]
