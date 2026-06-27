# Agent Instructions — RoomGrub Backend

## API Convention

All routes use the `/api/v1` prefix with no trailing slashes.

- Resource collections: `@router.get("")`
- Resource items: `@router.get("/{id}")`
- Actions: `@router.post("/<action>")`

---

## Layered Architecture

| Layer | Location | Responsibility |
|-------|----------|----------------|
| Router | `app/api/<domain>/api.py` | HTTP only: parse request, call service, return response. No business logic. |
| Schema | `app/api/<domain>/schemas.py` | Pydantic models for request bodies and response shapes. |
| Service | `app/services/<domain>/` | All business logic, role enforcement, guards, calculations. |
| Model | `app/models/<domain>/` | Raw SQL query functions. No business logic. Returns rows/dicts. |
| Dependency | `app/dependencies/` | FastAPI DI: auth verification, room access guards. |

**Rule of thumb:**
- If it's about HTTP (status codes, request parsing, response shape) → router
- If it's a business rule (who can do what, how amounts are calculated) → service
- If it talks to the database → model

---

## Raw SQL — Mandatory Pattern

All database queries use raw parameterized SQL. Never define ORM model classes.

```python
# In app/models/<domain>/<domain>_model.py
from sqlalchemy import text

def get_room_by_id(conn, room_id: int):
    result = conn.execute(
        text("SELECT id, admin, budget, members FROM Rooms WHERE id = :room_id"),
        {"room_id": room_id}
    )
    return result.fetchone()
```

Never use `Base`, `Column`, `relationship()`, or any SQLAlchemy declarative/mapped ORM patterns.

---

## Adding a New Domain

Follow this checklist when implementing a new API domain:

1. **Create folder structure:**
   ```
   app/api/<domain>/
     __init__.py
     api.py        ← router
     schemas.py    ← pydantic models
   app/models/<domain>/
     __init__.py
     <domain>_model.py   ← SQL functions
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
   app.include_router(<domain>_router, dependencies=[Depends(get_current_user)])
   ```

4. **Write schemas** in `schemas.py` before implementing the route.

5. **Write SQL functions** in `<domain>_model.py` — one function per query.

6. **Write service functions** in `<domain>_services.py` — call model functions, apply business rules.

7. **Implement route handlers** in `api.py` — call service, return response schema.

---

## Business Rule Guardrails

These rules **must** be enforced in the service layer, not the router:

| Rule | Where enforced |
|------|---------------|
| Only Admins can settle, remove members, create invites, delete room | `require_room_admin` dependency + service check |
| Admin cannot demote themselves | service layer |
| Admin cannot remove themselves (use `/members/me` to exit) | service layer |
| Non-admin cannot exit if they are the sole Admin | service layer |
| Room delete blocked if any unsettled expenses exist | `rooms_services.py` |
| Settle-all: re-verify pending amounts server-side (0.01 tolerance) | `splits_services.py` |
| Invite accept is idempotent — already a member → success, no duplicate | `invites_services.py` |
| Invite expires after 7 days | checked at validate and accept time in `invites_services.py` |

---

## Error Handling Pattern

```python
# In routers — HTTP exceptions only
from fastapi import HTTPException

@router.delete("/{room_id}/members/{member_id}")
def remove_member(room_id: int, member_id: int, ...):
    try:
        members_service.remove_member(conn, room_id, member_id, current_user)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# In services — plain exceptions
def remove_member(conn, room_id, member_id, current_user):
    if current_user.email == member_email:
        raise ValueError("Admin cannot remove themselves. Use /members/me to exit.")
```

---

## SQL Patterns

Always use `text()` with named bound parameters:

```python
from sqlalchemy import text

# Correct
conn.execute(text("SELECT * FROM Spendings WHERE room = :room_id AND settled IS NOT TRUE"), {"room_id": room_id})

# Never — SQL injection risk
conn.execute(f"SELECT * FROM Spendings WHERE room = {room_id}")
```

For inserts that return the new row id:
```python
result = conn.execute(
    text("INSERT INTO Rooms (admin, budget) VALUES (:admin, :budget) RETURNING id"),
    {"admin": admin_email, "budget": budget}
)
new_id = result.fetchone()[0]
```

---

## DB Session

Use `db_conn()` from `db/engine.py` as a FastAPI dependency. It handles commit and rollback automatically.

```python
from fastapi import Depends
from db.engine import db_conn

@router.post("")
def create_room(body: RoomCreate, conn=Depends(db_conn), ...):
    ...
```

Do not manually commit or rollback — let `db_conn()` manage the transaction.
