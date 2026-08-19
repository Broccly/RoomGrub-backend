from pydantic import BaseModel


class UpsertUserRow(BaseModel):
    id: int
    uid: str
    email: str
    name: str | None
    profile: str | None
    inserted: bool
