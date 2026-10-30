from pydantic import BaseModel


class InsertRoomResponse(BaseModel):
    id: int


class ListRoomsResponse(BaseModel):
    id: int
    members: int
    admin: str | None
    admin_user_id: int | None
    admin_name: str | None


class MemberPreviewRow(BaseModel):
    room_id: int
    profile: str | None
    label: str


class MemberStatRow(BaseModel):
    user_id: int
    name: str | None
    profile: str | None
    pending_amount: float