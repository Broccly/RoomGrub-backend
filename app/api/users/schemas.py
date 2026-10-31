from typing import Annotated
from pydantic import BaseModel, StringConstraints, field_validator

UserName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


class UpdateMeRequest(BaseModel):
    # Leave a field out to keep it. `avatar: null` removes the avatar; `name` can't be null.
    name: UserName | None = None
    # URL of an image on an allowed host (AVATAR_ALLOWED_HOSTS). Stored in Users.profile.
    avatar: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("name cannot be null")
        return value


class MeResponse(BaseModel):
    id: int
    email: str | None
    name: str | None
    # Avatar URL; when missing, the app draws initials from `name`.
    profile: str | None
    # registered | guest | placeholder
    type: str
