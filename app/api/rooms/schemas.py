from typing import Annotated
from pydantic import BaseModel, StringConstraints

RoomName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


class CreateRoomRequest(BaseModel):
    # Optional so clients that send no body keep working.
    name: RoomName | None = None


class RenameRoomRequest(BaseModel):
    name: RoomName


class RoomResponse(BaseModel):
    id: int
    # None for rooms created before rooms had names.
    name: str | None
    members: int
    # Email of the room's longest-standing Admin; None if that Admin has no email.
    admin: str | None
    admin_user_id: int | None
    admin_name: str | None


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
