from sqlalchemy import URL, Connection, Engine, create_engine
from typing import Any, Generator
from db.config import (
  get_db_host,
  get_db_name,
  get_db_password,
  get_db_pool_size,
  get_db_port,
  get_db_user,
  get_db_max_overflow,
  validate_env,
)

def _get_db_url() -> URL:
  # URL.create escapes each part, so a password containing @ : / # ? % stays intact
  return URL.create(
    "postgresql",
    username = get_db_user(),
    password = get_db_password(),
    host = get_db_host(),
    port = int(get_db_port()),
    database = get_db_name(),
  )


def get_sql_engine() -> Engine:
  validate_env()
  return create_engine(
    _get_db_url(),
    pool_size = get_db_pool_size(),
    max_overflow = get_db_max_overflow()
  )


_engine: Engine | None = None

def _get_engine() -> Engine:
  global _engine
  if _engine is None:
    _engine = get_sql_engine()
  return _engine


def db_conn() -> Generator[Connection, Any, None]:
  with _get_engine().connect() as conn:
    try:
      yield conn
    except Exception as e:
      conn.rollback()
      raise e
    conn.commit()