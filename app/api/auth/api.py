import redis
from fastapi import APIRouter, Depends
from sqlalchemy import Connection
from db.engine import db_conn
from db.redis_client import redis_conn
from app.api.auth.schemas import LoginRequest, LoginResponse
from app.services.auth.auth_services import login

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


@router.post("/login", response_model=LoginResponse)
def login_endpoint(
    body: LoginRequest,
    conn: Connection = Depends(db_conn),
    redis_client: redis.Redis = Depends(redis_conn),
) -> LoginResponse:
    return login(conn, body.provider, body.token, redis_client)
