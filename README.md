# RoomGrub Backend

Standalone **Python FastAPI** backend for RoomGrub — a shared-expense tracker for roommates. Extracted from the RoomGrub Next.js monolith to serve both the web app and the Android app via a single REST API.

## What it does

- Rooms: create and manage shared household groups
- Expenses: log purchases, track who spent what
- Splits: calculate pending amounts per member, settle balances
- Members: manage roles (Admin / Member), invite via link
- Notifications: in-app activity log + web push

## Tech stack

- **FastAPI** — REST API framework
- **PostgreSQL** (Supabase) — existing database, no migration needed
- **Raw SQL** — all DB queries are parameterized SQL, no ORM
- **Supabase Auth** — JWT verification for every request
- **Pydantic v2** — request/response validation

## Quick start

```bash
# Install dependencies
pip install -r requirements.txt

# Copy env and fill in values
cp .env.example .env

# Run dev server
uvicorn main:app --reload --port 8000
```

API docs available at `http://localhost:8000/docs` once running.

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, project structure, API surface |
| [docs/DOMAIN.md](docs/DOMAIN.md) | Entity model, business rules, relationships |
| [docs/AUTH.md](docs/AUTH.md) | JWT verification and auth flow |
| [docs/PLAN.md](docs/PLAN.md) | Phased implementation plan |
| [docs/TODOS.md](docs/TODOS.md) | Implementation checklist |
| [docs/SETUP.md](docs/SETUP.md) | Local dev setup guide |

## Project structure

```
main.py               # App entry point
app/
  api/<domain>/       # Route handlers + Pydantic schemas
  models/<domain>/    # Raw SQL query functions
  services/<domain>/  # Business logic
  dependencies/       # FastAPI DI: auth, room access guards
db/
  config.py           # Env var getters
  engine.py           # SQLAlchemy connection engine + db_conn()
docs/                 # All documentation
tests/                # pytest test suite
```
