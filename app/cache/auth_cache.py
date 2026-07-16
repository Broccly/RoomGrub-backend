import json
import logging
import redis
from db.config import get_cache_ttl_seconds
from db.redis_circuit import is_open, trip, reset

logger = logging.getLogger(__name__)


def _user_key(user_id: int) -> str:
  return f"auth:user:{user_id}"


def _room_access_key(user_id: int, room_id: int) -> str:
  return f"access:{user_id}:{room_id}"


def get_cached_user(client: redis.Redis, user_id: int) -> dict | None:
  if is_open():
    return None
  try:
    raw = client.get(_user_key(user_id))
    reset()
    return json.loads(raw) if raw else None
  except (redis.RedisError, ValueError) as e:
    trip()
    logger.warning("Redis unavailable, falling back to DB for get_cached_user: %s", e)
    return None


def set_cached_user(client: redis.Redis, user_id: int, user: dict) -> None:
  if is_open():
    return
  try:
    client.setex(_user_key(user_id), get_cache_ttl_seconds(), json.dumps(user))
    reset()
  except (redis.RedisError, ValueError) as e:
    trip()
    logger.warning("Redis unavailable, skipping set_cached_user: %s", e)


def invalidate_cached_user(client: redis.Redis, user_id: int) -> None:
  if is_open():
    return
  try:
    client.delete(_user_key(user_id))
    reset()
  except redis.RedisError as e:
    trip()
    logger.warning("Redis unavailable, skipping invalidate_cached_user: %s", e)


def get_cached_room_access(client: redis.Redis, user_id: int, room_id: int) -> dict | None:
  if is_open():
    return None
  try:
    raw = client.get(_room_access_key(user_id, room_id))
    reset()
    return json.loads(raw) if raw else None
  except (redis.RedisError, ValueError) as e:
    trip()
    logger.warning("Redis unavailable, falling back to DB for get_cached_room_access: %s", e)
    return None


def set_cached_room_access(client: redis.Redis, user_id: int, room_id: int, membership: dict) -> None:
  if is_open():
    return
  try:
    client.setex(_room_access_key(user_id, room_id), get_cache_ttl_seconds(), json.dumps(membership))
    reset()
  except (redis.RedisError, ValueError) as e:
    trip()
    logger.warning("Redis unavailable, skipping set_cached_room_access: %s", e)


def invalidate_cached_room_access(client: redis.Redis, user_id: int, room_id: int) -> None:
  if is_open():
    return
  try:
    client.delete(_room_access_key(user_id, room_id))
    reset()
  except redis.RedisError as e:
    trip()
    logger.warning("Redis unavailable, skipping invalidate_cached_room_access: %s", e)


def invalidate_all_room_access_for_room(client: redis.Redis, room_id: int, user_ids: list[int]) -> None:
  if not user_ids:
    return
  if is_open():
    return
  try:
    client.delete(*(_room_access_key(user_id, room_id) for user_id in user_ids))
    reset()
  except redis.RedisError as e:
    trip()
    logger.warning("Redis unavailable, skipping invalidate_all_room_access_for_room: %s", e)
