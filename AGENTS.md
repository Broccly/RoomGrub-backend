# Agent Instructions — RoomGrub Backend

> `CLAUDE.md` is a symlink to this file. Edit `AGENTS.md`.

## What is this repo

RoomGrub Backend is a standalone **Python FastAPI** service extracted from the RoomGrub Next.js monolith. It provides a REST API for managing shared household expenses — rooms, members, expenses, splits, invites, and push notifications. It is consumed by both the RoomGrub web app (Next.js) and the Android app (React Native).

## Key docs

Read these before working on any feature:

| Doc | What it covers |
|-----|----------------|
| `docs/DOMAIN.md` | All entities (Users, Rooms, Spendings, SpendingSplits, RoomBalanceSummary, Invite, ...), field definitions, business rules |
| `docs/ARCHITECTURE.md` | System design, project structure, full API surface, caching, events, push |
| `docs/AUTH.md` | Login flow, RoomGrub JWT, role guard patterns |
| `docs/SETUP.md` | Env var reference, external services (Google, Redis, Firebase) |
| `docs/MIGRATIONS.md` | Writing and applying dbmate migrations |
| `docs/PLAN.md` | Project status by phase — what's done, what's next |
| `docs/TODOS.md` | Open work and known code-vs-convention gaps |
| `tests/README.md` | Test layout, isolation, fixtures |

When you change behaviour, update the doc that describes it and add an entry to `CHANGELOG.md` under `[Unreleased]` in the same change.

---

## Layered Architecture

| Layer | Location | Responsibility |
|-------|----------|----------------|
| Router | `app/api/<domain>/api.py` | HTTP only: parse request, call service, return response. No business logic. |
| Schema | `app/api/<domain>/schemas.py` | Pydantic models for request bodies and response shapes. |
| Service | `app/services/<domain>/` | All business logic, role enforcement, guards, calculations. |
| Model | `app/models/<domain>/<domain>_model.py` | Raw SQL query functions. No business logic. Returns dicts. |
| Row schema | `app/models/<domain>/schemas.py` | Pydantic validators for rows returned by model queries. |
| Dependency | `app/dependencies/` | FastAPI DI: `get_current_user`, `require_room_member`, `require_room_admin`, `require_room_non_admin`. |
| Cache | `app/cache/` | Redis cache-aside helpers. Fail-open — never let Redis fail a request. |
| Events | `app/events/publisher.py` | `publish_event` → Redis stream `rg:emails`. Never raises. |
| DB | `db/engine.py`, `db/redis_client.py` | Connections only: `db_conn()` and `redis_conn()` dependencies. |

**Rule of thumb:**
- If it's about HTTP (status codes, request parsing, response shape) → router
- If it's a business rule (who can do what, how amounts are calculated) → service
- If it talks to the database → model

---

## API Convention

All routes use the `/api/v1` prefix with **no trailing slashes**.

- Resource collections: `@router.get("")`
- Resource items: `@router.get("/{id}")`
- Actions: `@router.post("")` or `@router.post("/<action>")`
- Router prefix defined on `APIRouter(prefix="/api/v1/<domain>", tags=["..."])`. Room-scoped domains use `prefix="/api/v1/rooms"` with `/{room_id}/<resource>` paths.
- Every route declares `response_model` (or a 204 status) and a return type annotation.

---

## Raw SQL — Mandatory Pattern

**This project uses raw parameterized SQL. Do not introduce SQLAlchemy ORM model classes.** SQLAlchemy is present only for the connection engine and pool in `db/engine.py`.

```python
# In app/models/<domain>/<domain>_model.py
from sqlalchemy import Connection, text
from app.models.notifications.schemas import NotificationRow

def get_notifications(conn: Connection, room_id: int, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        text("""
            SELECT id, room_id, activity_type, title, message, created_at
            FROM notifications
            WHERE room_id = :room_id
            ORDER BY created_at DESC
            LIMIT :limit
        """),
        {"room_id": room_id, "limit": limit},
    ).fetchall()
    return [NotificationRow(**r._mapping).model_dump() for r in rows]
```

- Always `text()` with named bound parameters. Never interpolate values or build SQL with f-strings.
- Mixed-case tables must be double-quoted: `"Users"`, `"Rooms"`, `"UserRooms"`, `"Spendings"`, `"SpendingSplits"`, `"RoomBalanceSummary"`, `"Invite"`. So must the `"user"` column on `"Spendings"`.
- Don't use `:param::type` casts — SQLAlchemy's `text()` reads `::` as an escaped colon. Use `CAST(:param AS type)`.
- Validate returned rows through a Pydantic row schema in `app/models/<domain>/schemas.py` and return plain dicts.
- For inserts that need the new id, use `RETURNING`:

```python
row = conn.execute(text('INSERT INTO "Rooms" DEFAULT VALUES RETURNING id')).fetchone()
```

Never use `Base`, `Column`, `relationship()`, or any SQLAlchemy declarative/mapped ORM patterns.

---

## DB Session

Use `db_conn()` from `db/engine.py` as a FastAPI dependency. It opens one transaction per request, commits on success and rolls back on error.

```python
from fastapi import Depends
from sqlalchemy import Connection
from db.engine import db_conn

@router.post("", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
def create_room(
    conn: Connection = Depends(db_conn),
    current_user: dict = Depends(get_current_user),
) -> RoomResponse:
    return rooms_services.create_room(conn, current_user=current_user)
```

Do not manually commit or rollback — let `db_conn()` manage the transaction. Work that must not abort the surrounding transaction if it fails (see `push_service.send_push`) goes in a savepoint: `with conn.begin_nested():`.

Schema changes are dbmate migrations in `db/migrations/` — see `docs/MIGRATIONS.md`.

---

## Authentication

- `POST /api/v1/auth/login` exchanges a Google/Facebook token for a RoomGrub JWT. There is no Supabase Auth.
- Every protected route depends on `get_current_user` from `app/dependencies/current_user.py`, which verifies the JWT and returns the user as a dict (`id`, `email`, `name`, `profile`).
- Room-scoped routes depend on a guard from `app/dependencies/room_access.py` instead: `require_room_member`, `require_room_admin` or `require_room_non_admin`. Each returns `{"id", "role", "user"}`; pass `membership["user"]` to the service.
- Auth is declared per route — routers are included in `main.py` without global dependencies.
- Always take `room_id` from the path so the guard checks the same room the handler acts on.
- See `docs/AUTH.md` for the full flow.

---

## Error Handling

- **Routers and dependencies**: raise `HTTPException` with appropriate status codes.
- **Services**: raise plain Python exceptions (`ValueError`, `PermissionError`, ...). No `fastapi` imports. Routers catch and convert.
- **Models**: raise only on DB errors — don't embed business rules here.

```python
# In services — plain exceptions
def remove_member(conn, room_id, user_id, current_user, redis_client):
    if user_id == current_user["id"]:
        raise ValueError("Admin cannot remove themselves. Use /members/me to exit.")

# In routers — convert to HTTP
@router.delete("/{room_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(room_id: int, user_id: int, ...) -> None:
    try:
        members_services.remove_member(conn, room_id, user_id, membership["user"], redis_client)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

> **Known gap:** most existing services still raise `HTTPException` directly. That is debt, tracked in `docs/TODOS.md` — do not copy it. Write new service code to the rule above, and convert a service function when you touch it.

---

## Side effects: cache, events, push

- **Cache**: after any write that changes room membership or a role, call the matching `invalidate_*` helper from `app/cache/auth_cache.py`.
- **Events**: `publish_event(redis_client, "<type>", payload)` for anything that should trigger an email. Document new event types in `docs/ARCHITECTURE.md`.
- **Push**: `send_push(conn, user_ids, title=..., body=..., data=...)` from `app/services/notifications/push_service.py`. `data` values must be strings.
- All three are best-effort: they log and continue on failure. Never let one fail or roll back the request.

---

## Adding a New Domain

1. **Create folder structure:**
   ```
   app/api/<domain>/
     __init__.py
     api.py        ← router
     schemas.py    ← pydantic request/response models
   app/models/<domain>/
     __init__.py
     <domain>_model.py   ← SQL functions
     schemas.py          ← pydantic row validators
   app/services/<domain>/
     __init__.py
     <domain>_services.py  ← business logic
   ```

2. **Define the router** in `api.py`:
   ```python
   from fastapi import APIRouter
   router = APIRouter(prefix="/api/v1/<domain>", tags=["<Domain>"])
   ```

3. **Register in `main.py`:**
   ```python
   from app.api.<domain>.api import router as <domain>_router
   app.include_router(<domain>_router)
   ```

4. **Write schemas** in `schemas.py` before implementing the route.

5. **Write SQL functions** in `<domain>_model.py` — one function per query.

6. **Write service functions** in `<domain>_services.py` — call model functions, apply business rules.

7. **Implement route handlers** in `api.py` — pick the auth guard, call the service, convert its exceptions, return the response schema.

8. **Add tests** in `tests/e2e/test_<domain>.py`, and document the routes in `docs/ARCHITECTURE.md`.

---

## Business Rule Guardrails

These rules **must** keep holding. Full detail in `docs/DOMAIN.md`.

| Rule | Where enforced |
|------|---------------|
| Only Admins can edit/delete expenses, add expenses for others, change roles, remove members, create invites, settle, delete the room | `require_room_admin` dependency |
| Only non-admins can exit a room | `require_room_non_admin` dependency + `members_services.exit_room` |
| Admin cannot demote themselves | `members_services.change_member_role` |
| Admin cannot remove themselves | `members_services.remove_member` |
| A member with a non-zero balance cannot exit or be removed | `members_services` |
| Room delete blocked if any unsettled expenses exist | `rooms_services.delete_room` |
| Expense amount must be > 0; explicit participants must all be room members | `expenses_services` |
| Every expense add/edit/delete updates `SpendingSplits` and `RoomBalanceSummary` in the same transaction | `expenses_services` |
| Settle-all: re-verify client-sent balances server-side (0.01 tolerance) | `splits_services.settle_all` |
| Invite accept is idempotent — already a member → success, no duplicate | `invites_services.accept_invite` |
| Invite expires after 7 days | checked at validate and accept time in `invites_services` |

---

## Do not

- No SQLAlchemy ORM model classes (`Base`, `Column`, `relationship()`) — ever
- No async SQLAlchemy — use sync connections only
- No trailing slashes on routes
- No f-string SQL — always use parameterized queries (`text()` with bound params)
- No business logic in routers — put it in services
- No HTTP concerns in services — no `HTTPException`, no status codes
- No manual `commit()` / `rollback()`
- No hard dependency on Redis or Firebase — both must fail open

---

## Running the app

```bash
uvicorn main:app --reload --port 8000
```

Docs at `http://localhost:8000/docs`.

## Running tests

```bash
pytest -v
```

e2e tests live in `tests/e2e/` and need the test database (`./scripts/migrate_test_db.sh`); unit tests live in `tests/unit/`. See `tests/README.md`.
