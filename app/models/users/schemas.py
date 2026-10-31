from pydantic import BaseModel


class UserRow(BaseModel):
    id: int
    email: str | None
    name: str | None
    profile: str | None
    type: str
