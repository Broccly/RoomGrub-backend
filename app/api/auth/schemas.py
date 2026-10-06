from pydantic import BaseModel


class LoginRequest(BaseModel):
    provider: str
    token: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: int
    email: str
    name: str | None
    profile: str | None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str


class LoginResponse(TokenResponse):
    user: UserResponse


class ErrorResponse(BaseModel):
    detail: str
