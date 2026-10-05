Scaffold a new API domain for RoomGrub backend.

To add a new domain (replace `<domain>` with e.g. `expenses`, `members`, `invites`):

## Checklist

### 1. Create folder structure
```
app/api/<domain>/
  __init__.py
  api.py          ← router and route handlers
  schemas.py      ← Pydantic request/response models

app/models/<domain>/
  __init__.py
  <domain>_model.py   ← raw SQL query functions

app/services/<domain>/
  __init__.py
  <domain>_services.py  ← business logic
```

### 2. Router boilerplate (`app/api/<domain>/api.py`)
```python
from fastapi import APIRouter, Depends
from db.engine import db_conn
from app.dependencies.current_user import get_current_user
from app.api.<domain>.schemas import ...
from app.services.<domain>.<domain>_services import ...

router = APIRouter(prefix="/api/v1/<domain>", tags=["<Domain>"])

@router.get("")
def list_<domain>(conn=Depends(db_conn), current_user=Depends(get_current_user)):
    return <domain>_service.list(conn, current_user)
```

### 3. Register router in `main.py`
```python
from app.api.<domain>.api import router as <domain>_router
app.include_router(<domain>_router)
```

### 4. Write schemas before implementing routes
Keep request models and response models clearly separated in `schemas.py`.

### 5. SQL functions go in `<domain>_model.py`
One function per query. Use `text()` with named bound parameters only — no f-strings, no ORM.

### 6. Business logic goes in `<domain>_services.py`
Role checks, guards, and calculations live here. Services raise plain exceptions; routers catch and convert to `HTTPException`. (Older services still raise `HTTPException` directly — do not copy that; see `docs/TODOS.md`.)

### 7. Reference
- See `AGENTS.md` for the full pattern guide
- See `docs/TODOS.md` for open work
- See `docs/DOMAIN.md` for table names, column names, and business rules
