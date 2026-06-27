# CLAUDE.md — RoomGrub Backend

## What is this repo

RoomGrub Backend is a standalone **Python FastAPI** service extracted from the RoomGrub Next.js monolith. It provides a REST API for managing shared household expenses — rooms, members, expenses, splits, invites, and push notifications. It is consumed by both the RoomGrub web app (Next.js) and the Android app (React Native).

## Key docs

Read these before working on any feature:

| Doc | What it covers |
|-----|----------------|
| `docs/DOMAIN.md` | All entities (User, Room, Spendings, Balance, Invite, etc.), field definitions, business rules |
| `docs/ARCHITECTURE.md` | System design, actual project structure, full API surface |
| `docs/AUTH.md` | Supabase JWT verification flow, user sync, role guard patterns |
| `docs/PLAN.md` | Phased implementation plan — what's done, what's next |
| `docs/TODOS.md` | Granular implementation checklist with file paths |

## Architecture patterns

### Layer responsibilities

```
app/api/<domain>/api.py       → Router: thin, HTTP only. Validates input, calls service, returns response.
app/services/<domain>/        → Service: all business logic, role checks, guards, calculations.
app/models/<domain>/          → Model: raw SQL query functions only. No business logic here.
app/dependencies/             → FastAPI DI: get_current_user, require_room_member, require_room_admin.
db/engine.py                  → DB connection only. db_conn() is the session generator.
```

### Raw SQL — no ORM

**This project uses raw parameterized SQL. Do not introduce SQLAlchemy ORM model classes.**

SQLAlchemy is present only for the connection engine and pool in `db/engine.py`. Every database query is a raw SQL string with bound parameters executed via the session from `db_conn()`.

```python
# Correct
conn.execute(text("SELECT * FROM Rooms WHERE id = :room_id"), {"room_id": room_id})

# Never do this
class Room(Base):
    __tablename__ = "Rooms"
    ...
```

### Adding a new domain

When adding a new API domain (e.g., `expenses`):
1. Create `app/api/expenses/` with `api.py` and `schemas.py`
2. Create `app/models/expenses/expenses_model.py` — SQL query functions
3. Create `app/services/expenses/expenses_services.py` — business logic
4. Register the router in `main.py`

## API conventions

- All routes: `/api/v1/<resource>` prefix, **no trailing slashes**
- Collections: `@router.get("")`
- Items: `@router.get("/{id}")`
- Actions: `@router.post("")` or `@router.post("/<action>")`
- Router files: `app/api/<domain>/api.py`
- Schema files: `app/api/<domain>/schemas.py`
- Router prefix defined on `APIRouter(prefix="/api/v1/<domain>", tags=["..."])`

## DB access

Use `db_conn()` from `db/engine.py` as a FastAPI dependency:

```python
from db.engine import db_conn
from sqlalchemy import text

def get_rooms(conn):
    result = conn.execute(text("SELECT * FROM Rooms WHERE ..."), {...})
    return result.fetchall()
```

Always let the engine handle commit/rollback — `db_conn()` commits on success and rolls back on error.

## Authentication

- Every protected route depends on `get_current_user` from `app/dependencies/current_user.py`.
- The dependency verifies the Supabase JWT and returns the current user.
- Room-scoped guards: `require_room_member` and `require_room_admin` from `app/dependencies/room_access.py`.
- See `docs/AUTH.md` for the full JWT verification pattern.

## Error handling

- **Routers and dependencies**: raise `HTTPException` with appropriate status codes.
- **Services**: raise plain Python exceptions (`ValueError`, `PermissionError`). Routers catch and convert.
- **Models**: raise only on DB errors — don't embed business rules here.

## Do not

- No SQLAlchemy ORM model classes (`Base`, `Column`, `relationship()`) — ever
- No async SQLAlchemy — use sync sessions only
- No trailing slashes on routes
- No f-string SQL — always use parameterized queries (`text()` with bound params)
- No business logic in routers — put it in services
- No HTTP concerns in services — put them in routers

## Running the app

```bash
uvicorn main:app --reload --port 8000
```

Docs at `http://localhost:8000/docs`.

## Running tests

```bash
pytest -v
```

Test files live in `tests/`. See `docs/TODOS.md` for what tests need to be written.
