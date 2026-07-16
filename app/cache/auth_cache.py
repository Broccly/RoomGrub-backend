import json
import redis
from db.config import get_cache_ttl_seconds


def _user_key(user_id: int) -> str:
  return f"auth:user:{user_id}"


def _room_access_key(user_id: int, room_id: int) -> str:
  return f"access:{user_id}:{room_id}"


def get_cached_user(client: redis.Redis, user_id: int) -> dict | None:
  raw = client.get(_user_key(user_id))
  return json.loads(raw) if raw else None


def set_cached_user(client: redis.Redis, user_id: int, user: dict) -> None:
  client.setex(_user_key(user_id), get_cache_ttl_seconds(), json.dumps(user))


def invalidate_cached_user(client: redis.Redis, user_id: int) -> None:
  client.delete(_user_key(user_id))


def get_cached_room_access(client: redis.Redis, user_id: int, room_id: int) -> dict | None:
  raw = client.get(_room_access_key(user_id, room_id))
  return json.loads(raw) if raw else None


def set_cached_room_access(client: redis.Redis, user_id: int, room_id: int, membership: dict) -> None:
  client.setex(_room_access_key(user_id, room_id), get_cache_ttl_seconds(), json.dumps(membership))


def invalidate_cached_room_access(client: redis.Redis, user_id: int, room_id: int) -> None:
  client.delete(_room_access_key(user_id, room_id))


def invalidate_all_room_access_for_room(client: redis.Redis, room_id: int, user_ids: list[int]) -> None:
  if not user_ids:
    return
  client.delete(*(_room_access_key(user_id, room_id) for user_id in user_ids))
