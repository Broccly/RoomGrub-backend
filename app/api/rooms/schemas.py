from pydantic import BaseModel


class RoomResponse(BaseModel):
    id: int
    members: int
    admin: str


class MemberPreview(BaseModel):
    # Avatar photo URL; when missing, the app draws initials from `label`.
    profile: str | None
    label: str


class RoomListItem(RoomResponse):
    # The first few members by join date, enough to draw a room card's avatars.
    member_preview: list[MemberPreview]


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
