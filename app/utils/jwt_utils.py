import hashlib
import secrets
from datetime import datetime, timedelta, timezone
import jwt
from db.config import get_jwt_secret, get_jwt_access_expiry_minutes


def create_jwt(user: dict) -> str:
    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "exp": datetime.now(timezone.utc) + timedelta(minutes=get_jwt_access_expiry_minutes()),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm="HS256")


def access_token_expires_in() -> int:
    return get_jwt_access_expiry_minutes() * 60


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
