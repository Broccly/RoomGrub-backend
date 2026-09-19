import os

_REQUIRED_ENV_VARS = [
  "DB_NAME",
  "DB_HOST",
  "DB_PORT",
  "DB_USER",
  "DB_PASSWORD",
  "DB_POOL_SIZE",
  "DB_MAX_OVERFLOW",
  "JWT_SECRET",
  "REDIS_URL",
  "GOOGLE_CLIENT_ID",
]

def validate_env() -> None:
  missing = [key for key in _REQUIRED_ENV_VARS if key not in os.environ]
  if missing:
    raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

def get_db_name():
  return os.environ["DB_NAME"]

def get_db_host():
  return os.environ["DB_HOST"]

def get_db_port():
  return os.environ["DB_PORT"]

def get_db_user():
  return os.environ["DB_USER"]

def get_db_password():
  return os.environ["DB_PASSWORD"]

def get_db_pool_size():
  return int(os.environ["DB_POOL_SIZE"])

def get_db_max_overflow():
  return int(os.environ["DB_MAX_OVERFLOW"])

def get_jwt_secret():
  return os.environ["JWT_SECRET"]

def get_jwt_expiry_hours() -> int:
  return int(os.environ.get("JWT_EXPIRY_HOURS", "24"))

def get_redis_url():
  return os.environ["REDIS_URL"]

def get_cache_ttl_seconds() -> int:
  return int(os.environ.get("CACHE_TTL_SECONDS", "604800"))

def get_google_client_id():
  return os.environ["GOOGLE_CLIENT_ID"]

def get_firebase_credentials_json() -> str | None:
  return os.environ.get("FIREBASE_CREDENTIALS_JSON")