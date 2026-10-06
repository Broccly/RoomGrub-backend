from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class UpsertUserRow(BaseModel):
    id: int
    uid: str
    email: str
    name: str | None
    profile: str | None
    inserted: bool


class RefreshTokenRow(BaseModel):
    id: int
    user_id: int
    email: str
    family_id: UUID
    expires_at: datetime
    used_at: datetime | None
    revoked_at: datetime | None
