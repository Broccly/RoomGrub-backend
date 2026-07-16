import jwt
import redis
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import Connection, text
from db.engine import db_conn
from db.redis_client import redis_conn
from db.config import get_jwt_secret
from app.cache.auth_cache import get_cached_user, set_cached_user

bearer = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    conn: Connection = Depends(db_conn),
    redis_client: redis.Redis = Depends(redis_conn),
) -> dict:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing subject claim")

    user_id = int(user_id)

    cached = get_cached_user(redis_client, user_id)
    if cached is not None:
        return cached

    row = conn.execute(
        text('SELECT id, email, name, profile FROM "Users" WHERE id = :id'),
        {"id": user_id},
    ).fetchone()

    if not row:
        raise HTTPException(status_code=401, detail="User not found")

    user = dict(row._mapping)
    set_cached_user(redis_client, user_id, user)
    return user
