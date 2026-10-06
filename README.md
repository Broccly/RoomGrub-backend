# RoomGrub Backend

Standalone **Python FastAPI** backend for RoomGrub — a shared-expense tracker for roommates. Extracted from the RoomGrub Next.js monolith to serve both the web app and the Android app via a single REST API.

## What it does

- Rooms: create and manage shared household groups
- Expenses: log purchases, track who spent what
- Splits: choose who shares each expense, keep a running net balance per member, suggest who pays whom, settle the room
- Members: manage roles (Admin / Member), invite via link
- Push: Firebase Cloud Messaging to an expense's participants
- Events: welcome and settlement emails via a Redis stream

## Tech stack

- **FastAPI** — REST API framework
- **PostgreSQL** (Supabase-hosted in dev/prod; local Docker Postgres for local dev/test) — schema managed via [dbmate](https://github.com/amacneil/dbmate) migrations
- **Raw SQL** — all DB queries are parameterized SQL, no ORM
- **Auth** — Google / Facebook token exchanged at login for an app-issued short-lived access JWT (verified on every request) plus a rotating refresh token, so devices stay signed in
- **Redis (Upstash)** — cache-aside layer for auth/room-access checks (fails open to Postgres if unreachable) and the `rg:emails` event stream
- **Firebase Cloud Messaging** — push notifications (optional; disabled when unconfigured)
- **Pydantic v2** — request/response validation

## Setup

Everything below uses Docker for the database — no Supabase credentials needed to get started.

**Prerequisites**: Python 3.11+, Docker, [dbmate](https://github.com/amacneil/dbmate#installation).

1. **Clone the repo and enter it**

   ```bash
   git clone <repo-url> RoomGrub-backend
   cd RoomGrub-backend
   ```

2. **Create a virtualenv and install dependencies**

   ```bash
   python -m venv .venv
   source .venv/bin/activate      # .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

3. **Copy the env file** — works out of the box, no values to look up

   ```bash
   cp .env.example .env
   ```

   `REDIS_URL` is a placeholder by default — fill in a real Upstash `rediss://` connection string to enable caching. The app runs fine without it reachable (Redis errors fail open to Postgres), it just won't cache anything or publish events until it's set correctly. Login needs a real `GOOGLE_CLIENT_ID`, and push needs `FIREBASE_CREDENTIALS_JSON` — see [docs/SETUP.md](docs/SETUP.md) for every variable and how to obtain each one.

4. **Start both local Postgres containers** (dev DB + test DB)

   ```bash
   docker compose up -d
   ```

5. **Apply migrations to both**

   ```bash
   ./scripts/migrate_dev_db.sh
   ./scripts/migrate_test_db.sh
   ```

6. **Run the dev server**

   ```bash
   uvicorn main:app --reload --port 8000
   ```

   API docs at `http://localhost:8000/docs`, health check at `http://localhost:8000/health`.

7. **Run the tests**

   ```bash
   pytest -v
   ```

Making a schema change from here on? See [docs/MIGRATIONS.md](docs/MIGRATIONS.md).

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, project structure, API surface |
| [docs/DOMAIN.md](docs/DOMAIN.md) | Entity model, business rules, relationships |
| [docs/AUTH.md](docs/AUTH.md) | Login, access + refresh tokens, role guards |
| [docs/SETUP.md](docs/SETUP.md) | Env var reference, Google / Redis / Firebase setup |
| [docs/PLAN.md](docs/PLAN.md) | Project status by phase, what's next |
| [docs/TODOS.md](docs/TODOS.md) | Open work and shipped checklist |
| [docs/MIGRATIONS.md](docs/MIGRATIONS.md) | Writing and applying dbmate migrations |
| [tests/README.md](tests/README.md) | Test suite setup, isolation, fixtures |
| [AGENTS.md](AGENTS.md) | Conventions for contributors and AI agents (`CLAUDE.md` is a symlink to it) |
| [CHANGELOG.md](CHANGELOG.md) | Release history |

## Project structure

```
main.py               # App entry point
app/
  api/<domain>/       # Route handlers + Pydantic schemas
  models/<domain>/    # Raw SQL query functions
  services/<domain>/  # Business logic
  dependencies/       # FastAPI DI: auth, room access guards
  cache/
    auth_cache.py     # Cache-aside helpers for auth/room-access (fail-open, circuit breaker)
  events/
    publisher.py      # publish_event → Redis stream rg:emails
  utils/              # Provider token verification, JWT creation
db/
  config.py           # Env var getters
  engine.py           # SQLAlchemy connection engine + db_conn()
  redis_client.py     # Redis client singleton + redis_conn()
  redis_circuit.py    # In-process circuit breaker for Redis outages
  migrations/         # dbmate migrations
scripts/              # Migration helper scripts
docs/                 # All documentation
tests/
  e2e/                # API tests against the test-db container
  unit/               # Unit tests
```
