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

def get_jwt_access_expiry_minutes() -> int:
  access_expiry_minutes = int(os.environ.get("JWT_ACCESS_EXPIRY_MINUTES", "15"))
  if access_expiry_minutes <= 0:
    raise ValueError("JWT_ACCESS_EXPIRY_MINUTES must be positive")
  return access_expiry_minutes

def get_refresh_token_expiry_days() -> int:
  refresh_expiry_days = int(os.environ.get("REFRESH_TOKEN_EXPIRY_DAYS", "90"))
  if refresh_expiry_days <= 0:
    raise ValueError("REFRESH_TOKEN_EXPIRY_DAYS must be positive")
  return refresh_expiry_days

def get_redis_url():
  return os.environ["REDIS_URL"]

def get_cache_ttl_seconds() -> int:
  return int(os.environ.get("CACHE_TTL_SECONDS", "604800"))

def get_google_client_id():
  return os.environ["GOOGLE_CLIENT_ID"]

def get_firebase_credentials_json() -> str | None:
  return os.environ.get("FIREBASE_CREDENTIALS_JSON")
# Hosts an avatar URL may point at. Defaults to the Google and Facebook photo hosts so
# provider photos stay valid; add the S3 / R2 bucket host once uploads exist.
_DEFAULT_AVATAR_ALLOWED_HOSTS = "lh3.googleusercontent.com,platform-lookaside.fbsbx.com"

def get_avatar_allowed_hosts() -> set[str]:
  raw = os.environ.get("AVATAR_ALLOWED_HOSTS", _DEFAULT_AVATAR_ALLOWED_HOSTS)
  return {host.strip().lower() for host in raw.split(",") if host.strip()}
