from datetime import datetime, timedelta, timezone
import jwt
from sqlalchemy import Connection
from db.config import get_jwt_secret, get_jwt_expiry_hours
from app.models.auth.auth_model import upsert_user
from app.utils.auth_providers import verify_provider_token


def _create_jwt(user: dict) -> str:
    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=get_jwt_expiry_hours()),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm="HS256")


def login(conn: Connection, provider: str, token: str) -> dict:
    user_info = verify_provider_token(provider, token)
    user = upsert_user(
        conn,
        uid=f"{provider}:{user_info['email']}",
        email=user_info["email"],
        name=user_info["name"],
        profile=user_info["picture"],
    )
    return {
        "access_token": _create_jwt(user),
        "token_type": "bearer",
        "user": user,
    }
