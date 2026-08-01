from pydantic import BaseModel


class RoomResponse(BaseModel):
    id: int
    members: int
    admin: str


class RoomSummary(RoomResponse):
    total_spent: float
    pending_amount: float


class MemberStat(BaseModel):
    user_id: int
    name: str | None
    profile: str | None
    pending_amount: float


class DashboardResponse(BaseModel):
    room: RoomResponse
    members: list[MemberStat]
