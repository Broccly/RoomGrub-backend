import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import Connection
from app.models.auth.auth_model import (
    delete_dead_refresh_tokens,
    get_refresh_token_for_update,
    insert_refresh_token,
    mark_refresh_token_used,
    revoke_refresh_token_family,
    upsert_user,
)
from app.utils.auth_providers import verify_provider_token
from app.utils.jwt_utils import access_token_expires_in, create_jwt, generate_refresh_token, hash_refresh_token
from app.events.publisher import publish_event
from db.config import get_refresh_token_expiry_days
import redis

# A spent refresh token presented again within this window is a concurrent retry
# (two tabs, a request retried after a dropped response), not a replay.
REFRESH_REUSE_GRACE_SECONDS = 30


class InvalidRefreshTokenError(Exception):
    pass


def _issue_refresh_token(conn: Connection, user_id: int, family_id: uuid.UUID, now: datetime) -> str:
    token = generate_refresh_token()
    insert_refresh_token(
        conn,
        user_id=user_id,
        token_hash=hash_refresh_token(token),
        family_id=family_id,
        expires_at=now + timedelta(days=get_refresh_token_expiry_days()),
    )
    return token


def _token_pair(user: dict, refresh_token: str) -> dict:
    return {
        "access_token": create_jwt(user),
        "token_type": "bearer",
        "expires_in": access_token_expires_in(),
        "refresh_token": refresh_token,
    }


def login(conn: Connection, provider: str, token: str, redis_client: redis.Redis) -> dict:
    user_info = verify_provider_token(provider, token)
    user = upsert_user(
        conn,
        uid=f"{provider}:{user_info['email']}",
        email=user_info["email"],
        name=user_info["name"],
        profile=user_info["picture"],
    )
    if user["inserted"]:
        publish_event(redis_client, event_type="welcome", payload={"email": user_info["email"], "name": user_info["name"]})

    now = datetime.now(timezone.utc)
    delete_dead_refresh_tokens(conn, user["id"], now)
    # Each login starts its own family, so every device has an independent session.
    refresh_token = _issue_refresh_token(conn, user["id"], uuid.uuid4(), now)

    return {**_token_pair(user, refresh_token), "user": user}


def refresh(conn: Connection, refresh_token: str) -> dict:
    now = datetime.now(timezone.utc)
    row = get_refresh_token_for_update(conn, hash_refresh_token(refresh_token))
    if row is None or row["revoked_at"] is not None or row["expires_at"] <= now:
        raise InvalidRefreshTokenError("Invalid refresh token")

    if row["used_at"] is None:
        mark_refresh_token_used(conn, row["id"], now)
    elif now - row["used_at"] > timedelta(seconds=REFRESH_REUSE_GRACE_SECONDS):
        # Replay of a spent token: one of the two holders is not the user, so end
        # the whole session. The caller must let this write commit.
        revoke_refresh_token_family(conn, row["family_id"], now)
        raise InvalidRefreshTokenError("Invalid refresh token")

    new_refresh_token = _issue_refresh_token(conn, row["user_id"], row["family_id"], now)
    return _token_pair({"id": row["user_id"], "email": row["email"]}, new_refresh_token)


def logout(conn: Connection, refresh_token: str) -> None:
    row = get_refresh_token_for_update(conn, hash_refresh_token(refresh_token))
    if row is not None:
        revoke_refresh_token_family(conn, row["family_id"], datetime.now(timezone.utc))
