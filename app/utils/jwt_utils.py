from datetime import datetime, timedelta, timezone
import jwt
from db.config import get_jwt_secret, get_jwt_expiry_hours


def create_jwt(user: dict) -> str:
    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=get_jwt_expiry_hours()),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm="HS256")
