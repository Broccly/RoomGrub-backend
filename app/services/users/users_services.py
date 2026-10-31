from urllib.parse import urlparse
import redis
from sqlalchemy import Connection
from app.models.users.users_model import get_user, update_user_profile
from app.cache.auth_cache import invalidate_cached_user
from db.config import get_avatar_allowed_hosts

MAX_AVATAR_URL_LENGTH = 2048


def get_me(conn: Connection, user_id: int) -> dict:
    user = get_user(conn, user_id)
    if not user:
        raise LookupError("User not found")
    return user


def _validate_avatar(url: str) -> None:
    if len(url) > MAX_AVATAR_URL_LENGTH:
        raise ValueError(f"Avatar URL must be at most {MAX_AVATAR_URL_LENGTH} characters")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Avatar must be an https URL")
    if parsed.hostname.lower() not in get_avatar_allowed_hosts():
        raise ValueError("Avatar URL host is not allowed")


def update_me(conn: Connection, user_id: int, changes: dict, redis_client: redis.Redis) -> dict:
    """`changes` holds only the fields the client sent; an `avatar` of None removes it."""
    if not changes:
        raise ValueError("Nothing to update: send name and/or avatar")
    avatar = changes.get("avatar")
    if avatar is not None:
        _validate_avatar(avatar)

    user = update_user_profile(
        conn,
        user_id,
        name=changes.get("name"),
        set_name="name" in changes,
        profile=avatar,
        set_profile="avatar" in changes,
    )
    if not user:
        raise LookupError("User not found")
    invalidate_cached_user(redis_client, user_id)
    return user
