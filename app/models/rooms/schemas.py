from pydantic import BaseModel


class InsertRoomResponse(BaseModel):
    id: int


class ListRoomsResponse(BaseModel):
    id: int
    members: int
    admin: str | None


class MemberStatRow(BaseModel):
    user_id: int
    name: str | None
    profile: str | None
    pending_amount: float