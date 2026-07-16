import redis
from typing import Any, Generator
from db.config import get_redis_url


def _build_redis_client() -> redis.Redis:
  return redis.from_url(
    get_redis_url(),
    decode_responses=True,
    socket_connect_timeout=1,
    socket_timeout=1,
    retry_on_timeout=False,
  )


_client: redis.Redis | None = None

def _get_redis_client() -> redis.Redis:
  global _client
  if _client is None:
    _client = _build_redis_client()
  return _client


def redis_conn() -> Generator[redis.Redis, Any, None]:
  yield _get_redis_client()
