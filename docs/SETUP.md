# RoomGrub Backend — Local Setup

## Prerequisites

- Python 3.11+
- A Supabase project (the existing RoomGrub one)
- PostgreSQL access to the Supabase DB (connection string from Supabase Dashboard)

---

## 1. Clone / navigate to this folder

```bash
cd /path/to/Broccly/RoomGrub-backend
```

---

## 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate      # Linux / macOS
# .venv\Scripts\activate       # Windows
```

---

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

Core packages that will be in `requirements.txt`:

```
fastapi>=0.111
uvicorn[standard]>=0.29
sqlalchemy[asyncio]>=2.0
asyncpg>=0.29
pydantic>=2.7
pydantic-settings>=2.2
python-jose[cryptography]>=3.3   # JWT verification
pywebpush>=2.0                   # Web Push notifications
httpx>=0.27                      # async HTTP client (for tests)
pytest>=8.0
pytest-asyncio>=0.23
```

---

## 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_JWT_SECRET=your-jwt-secret          # Dashboard → Settings → API → JWT Secret
SUPABASE_SERVICE_ROLE_KEY=your-service-key   # Dashboard → Settings → API → service_role

# Database (direct connection, not pooler)
DATABASE_URL=postgresql+asyncpg://postgres:password@db.your-project.supabase.co:5432/postgres

# VAPID (copy from existing .env in RoomGrub Next.js)
VAPID_SUBJECT=mailto:your-email@example.com
VAPID_PUBLIC_KEY=your-vapid-public-key
VAPID_PRIVATE_KEY=your-vapid-private-key

# App
APP_URL=http://localhost:8000
CORS_ORIGINS=http://localhost:3000,http://localhost:8081
```

### Where to find these values

| Variable              | Location                                                                 |
|-----------------------|--------------------------------------------------------------------------|
| `SUPABASE_JWT_SECRET` | Supabase Dashboard → Project Settings → API → JWT Settings → JWT Secret  |
| `DATABASE_URL`        | Supabase Dashboard → Project Settings → Database → Connection string     |
| `VAPID_*`             | Copy from `RoomGrub/.env.local` — same keys, no regeneration needed      |

---

## 5. Run the development server

```bash
uvicorn app.main:app --reload --port 8000
```

API docs available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health check: http://localhost:8000/health

---

## 6. Run tests

```bash
pytest
# or with verbose output:
pytest -v
```

Tests use a separate test database or transaction rollback per test — see `tests/conftest.py`.

---

## 7. Connecting the Next.js app locally

In `RoomGrub/.env.local`, set:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

The Next.js app will call this FastAPI backend instead of using Server Actions.

---

## 8. Connecting the Android app locally

In `RoomGrub-native`, update the API base URL config to point to your machine's local IP (not `localhost`, since the Android emulator uses a different network):

```
http://10.0.2.2:8000    # Android emulator
http://192.168.x.x:8000 # Physical device on same WiFi
```

---

## Database Notes

- The schema already exists in Supabase — no migrations are needed to get started.
- If schema changes are needed later, use Alembic:
  ```bash
  alembic init alembic
  alembic revision --autogenerate -m "description"
  alembic upgrade head
  ```
- Supabase Row Level Security (RLS) is **not relied on** for this backend. All access control is enforced at the FastAPI service layer. The service role key bypasses RLS.

---

## Project Structure Quick Reference

```
app/
├── main.py          # App factory
├── config.py        # Env var config
├── database.py      # DB engine + session
├── models/          # SQLAlchemy ORM models
├── schemas/         # Pydantic request/response models
├── routers/         # Route handlers
├── services/        # Business logic
├── dependencies/    # FastAPI dependencies (auth, role guards)
└── utils/           # Push notifications, pagination helpers
```

See `ARCHITECTURE.md` for the full structure and `DOMAIN.md` for the data model.
