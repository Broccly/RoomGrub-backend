import redis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Connection
from db.engine import db_conn
from db.redis_client import redis_conn
from app.dependencies.current_user import get_current_user
from app.api.users.schemas import MeResponse, UpdateMeRequest
from app.services.users import users_services

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


@router.get("/me", response_model=MeResponse)
def get_me(
    conn: Connection = Depends(db_conn),
    current_user: dict = Depends(get_current_user),
) -> MeResponse:
    try:
        return users_services.get_me(conn, current_user["id"])
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/me", response_model=MeResponse)
def update_me(
    body: UpdateMeRequest,
    conn: Connection = Depends(db_conn),
    current_user: dict = Depends(get_current_user),
    redis_client: redis.Redis = Depends(redis_conn),
) -> MeResponse:
    changes = body.model_dump(include=body.model_fields_set)
    try:
        return users_services.update_me(conn, current_user["id"], changes, redis_client)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
