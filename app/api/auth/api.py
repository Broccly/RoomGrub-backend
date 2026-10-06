import redis
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import Connection
from db.engine import db_conn
from db.redis_client import redis_conn
from app.api.auth.schemas import (
    ErrorResponse,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
)
from app.services.auth import auth_services

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


@router.post("/login", response_model=LoginResponse)
def login_endpoint(
    body: LoginRequest,
    conn: Connection = Depends(db_conn),
    redis_client: redis.Redis = Depends(redis_conn),
) -> LoginResponse:
    return auth_services.login(conn, body.provider, body.token, redis_client)


@router.post("/refresh", response_model=TokenResponse, responses={401: {"model": ErrorResponse}})
def refresh_endpoint(
    body: RefreshRequest,
    conn: Connection = Depends(db_conn),
) -> TokenResponse | JSONResponse:
    try:
        return auth_services.refresh(conn, body.refresh_token)
    except auth_services.InvalidRefreshTokenError as e:
        # Returned, not raised: raising would make db_conn() roll back, undoing the
        # family revocation that reuse detection has just written.
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": str(e)})


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout_endpoint(
    body: LogoutRequest,
    conn: Connection = Depends(db_conn),
) -> None:
    auth_services.logout(conn, body.refresh_token)
