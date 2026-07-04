from sqlalchemy import Connection
from app.models.auth.auth_model import upsert_user
from app.utils.auth_providers import verify_provider_token
from app.utils.jwt_utils import create_jwt


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
        "access_token": create_jwt(user),
        "token_type": "bearer",
        "user": user,
    }
