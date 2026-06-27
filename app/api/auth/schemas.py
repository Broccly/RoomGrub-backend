from pydantic import BaseModel


class LoginRequest(BaseModel):
    provider: str
    token: str


class UserResponse(BaseModel):
    id: int
    email: str
    name: str | None
    profile: str | None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
