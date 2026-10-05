# RoomGrub Backend — Configuration & External Services

Getting the app running locally is covered by the **Setup** section of the
[README](../README.md): virtualenv, `cp .env.example .env`, `docker compose up -d`,
migrate, `uvicorn`. That path needs no external accounts.

This document is the reference for everything in `.env` and for wiring up the
external services (Google sign-in, Redis, Firebase) when you need the features
that depend on them.

---

## Environment variables

Loaded from `.env` by `python-dotenv` at startup (`main.py`). "Required"
variables are checked by `validate_env()` in `db/config.py` the first time a
database connection is opened — a missing one raises `RuntimeError` naming it.

### Database

| Variable | Required | Default in `.env.example` | Purpose |
|----------|----------|---------------------------|---------|
| `DB_NAME` | yes | `roomgrub` | Database name |
| `DB_HOST` | yes | `localhost` | Host |
| `DB_PORT` | yes | `5436` | Port (the `dev-db` container) |
| `DB_USER` | yes | `roomgrub_user` | Role |
| `DB_PASSWORD` | yes | `roomgrub_password` | Password |
| `DB_POOL_SIZE` | yes | `5` | SQLAlchemy pool size |
| `DB_MAX_OVERFLOW` | yes | `5` | SQLAlchemy pool overflow |

The defaults match `docker-compose.yml`'s `dev-db` service. To run against the
Supabase dev database instead, point these at it — and read
[MIGRATIONS.md](MIGRATIONS.md) before applying migrations there.

### Auth

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `JWT_SECRET` | yes | placeholder | HS256 signing key for RoomGrub JWTs. Use 32+ random characters. |
| `JWT_EXPIRY_HOURS` | no | `24` | Token lifetime |
| `GOOGLE_CLIENT_ID` | yes | placeholder | OAuth client ID that Google `id_token`s must be issued for |

### Redis

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `REDIS_URL` | yes | placeholder | Auth / room-access cache and the `rg:emails` event stream |
| `CACHE_TTL_SECONDS` | no | `604800` (7 days) | TTL for cached user and room-access entries |

### Push

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `FIREBASE_CREDENTIALS_JSON` | no | empty | Firebase service-account JSON, on one line. Push is disabled when unset. |

### Tests

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `TEST_DB_NAME`, `TEST_DB_HOST`, `TEST_DB_PORT`, `TEST_DB_USER`, `TEST_DB_PASSWORD` | for `pytest` | match the `test-db` container (`localhost:55432`) | The e2e suite refuses to run without them, so it can never fall back to a real database |
| `TEST_DB_POOL_SIZE`, `TEST_DB_MAX_OVERFLOW` | no | `5` | |

### Other

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `ENV` | no | `dev` | Environment label; not read by the app today |

---

## What works without external services

With the untouched `.env.example`:

| Feature | Works? | Notes |
|---------|--------|-------|
| API, database, tests | yes | |
| Caching | degrades | The placeholder `REDIS_URL` is unreachable; every cache call fails open to Postgres and the circuit breaker stops retrying for 30s at a time |
| Events (`welcome`, `expense_split`) | no | Publish fails, is logged, and the request succeeds anyway |
| Push | no | Skipped with a one-time warning |
| Login | no | Needs a real `GOOGLE_CLIENT_ID` (or a Facebook token) |

Without login you can still exercise the API: mint a token for an existing
user the same way the tests do.

```bash
python -c "
from dotenv import load_dotenv; load_dotenv()
from app.utils.jwt_utils import create_jwt
print(create_jwt({'id': 1, 'email': 'you@example.com'}))
"
```

The user must exist in `"Users"` with that `id`.

---

## Google sign-in

1. In Google Cloud Console → APIs & Services → Credentials, create (or reuse) an OAuth 2.0 client ID.
2. Set `GOOGLE_CLIENT_ID` to it.
3. The web and Android clients must request their `id_token` for **this same client ID** — the backend rejects tokens whose `aud` differs.

Facebook login needs no backend configuration: the token is checked against the Graph API, and the app must have been granted the `email` permission.

See [AUTH.md](AUTH.md) for the full flow.

---

## Redis (Upstash)

1. Create a Redis database on Upstash.
2. Copy its TLS connection string (`rediss://default:<password>@<host>:6379`) into `REDIS_URL`.

Any Redis 5+ works, including a local one (`redis://localhost:6379`) — streams (`XADD`) are the newest feature used.

---

## Firebase Cloud Messaging

1. In the Firebase console for the RoomGrub app → Project settings → Service accounts → **Generate new private key**.
2. Collapse the downloaded JSON to a single line and set it as `FIREBASE_CREDENTIALS_JSON`:

   ```bash
   echo "FIREBASE_CREDENTIALS_JSON=$(jq -c . fcm-key.json)" >> .env
   ```

3. Don't commit the key file — `fcm-key.json` is already in `.gitignore`.

The Firebase project must be the same one the Android app is built against, or FCM rejects the device tokens with a sender-ID mismatch (and the backend prunes them).

---

## Running

```bash
uvicorn main:app --reload --port 8000
```

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health check: http://localhost:8000/health

```bash
pytest -v
```

See [tests/README.md](../tests/README.md) for how the suite is isolated.

---

## Pointing the clients at a local backend

| Client | Base URL |
|--------|----------|
| Web (Next.js on `localhost:3000` / `3001`) | `http://localhost:8000` — both origins are already in the CORS allow-list |
| Android emulator | `http://10.0.2.2:8000` |
| Physical device on the same Wi-Fi | `http://<your-machine-ip>:8000` (run uvicorn with `--host 0.0.0.0`) |

---

## Deployment (Vercel)

`vercel.json` routes every request to `main.py` using `@vercel/python`. Set the
variables above in the Vercel project's environment settings — there is no
`.env` file in the deployed bundle. Apply migrations to the target database
before deploying code that depends on them.
