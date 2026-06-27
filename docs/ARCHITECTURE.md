# RoomGrub Backend — Architecture

## Overview

This is a standalone **Python FastAPI** backend extracted from the RoomGrub Next.js monolith. It serves both the RoomGrub web app (Next.js) and the RoomGrub Android app via a single REST API.

```
┌─────────────────────┐      ┌──────────────────────┐
│  RoomGrub Web       │      │  RoomGrub Android     │
│  (Next.js)          │      │  (React Native)       │
└────────┬────────────┘      └──────────┬────────────┘
         │  HTTP / JSON                 │
         └──────────────┬───────────────┘
                        ▼
            ┌───────────────────────┐
            │  RoomGrub FastAPI     │
            │  (this repo)          │
            │                       │
            │  ┌─────────────────┐  │
            │  │ Routers         │  │
            │  │  /auth          │  │
            │  │  /rooms         │  │
            │  │  /expenses      │  │
            │  │  /splits        │  │
            │  │  /members       │  │
            │  │  /invites       │  │
            │  │  /notifications │  │
            │  └────────┬────────┘  │
            │           │           │
            │  ┌────────▼────────┐  │
            │  │  Services /     │  │
            │  │  Business Logic │  │
            │  └────────┬────────┘  │
            │           │           │
            │  ┌────────▼────────┐  │
            │  │  Models /       │  │
            │  │  Raw SQL        │  │
            │  └────────┬────────┘  │
            └───────────────────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │   Supabase             │
            │   - PostgreSQL DB      │
            │   - Auth (JWT tokens)  │
            └───────────────────────┘
```

---

## Tech Stack

| Layer         | Choice                              | Reason                                       |
|---------------|-------------------------------------|----------------------------------------------|
| Framework     | FastAPI                             | Async, fast, typed, auto-docs                |
| DB Queries    | Raw SQL (parameterized)             | Full control, no ORM abstraction             |
| DB Connection | SQLAlchemy engine (sync)            | Connection pooling only — no ORM used        |
| DB            | Supabase PostgreSQL (existing)      | No migration needed for schema               |
| Auth          | Supabase JWT verification           | Reuse existing Supabase Auth                 |
| Push Notifs   | `pywebpush`                         | Web Push Protocol, replaces `web-push` npm   |
| Validation    | Pydantic v2                         | Built into FastAPI, replaces manual checks   |
| Config        | `.env` + per-var getter functions   | Simple, explicit, 12-factor                  |
| Tests         | `pytest`                            | Standard test runner                         |
| Migrations    | Alembic (if schema changes needed)  | Schema already exists in Supabase            |

> **No ORM.** SQLAlchemy is present only for the connection engine and pool (`db/engine.py`). All database interaction uses raw parameterized SQL strings in `app/models/`.

---

## Project Structure

```
RoomGrub-backend/
├── main.py                       # FastAPI app factory, CORS, router registration
│
├── app/
│   ├── api/                      # Route handlers — one folder per domain
│   │   ├── auth/
│   │   │   ├── api.py            # Route functions
│   │   │   └── schemas.py        # Pydantic request/response models
│   │   ├── rooms/
│   │   │   ├── api.py
│   │   │   └── schemas.py
│   │   ├── expenses/             # (to be added)
│   │   ├── splits/               # (to be added)
│   │   ├── invites/              # (to be added)
│   │   └── friends/              # (to be added)
│   │
│   ├── models/                   # Raw SQL query functions — no ORM model classes
│   │   └── rooms/
│   │       └── rooms_model.py
│   │
│   ├── services/                 # Business logic, no HTTP concerns
│   │   └── rooms/
│   │       └── rooms_services.py
│   │
│   └── dependencies/             # FastAPI dependency injection
│       ├── current_user.py       # get_current_user — JWT verify via Supabase
│       └── room_access.py        # require_room_member, require_room_admin
│
├── db/
│   ├── config.py                 # Per-variable env getter functions
│   ├── engine.py                 # SQLAlchemy sync engine + db_conn() session generator
│   └── migrations/               # Alembic migrations (if schema changes needed)
│
├── docs/                         # Documentation
│   ├── ARCHITECTURE.md           # This file
│   ├── AUTH.md                   # JWT verification & auth flow
│   ├── DOMAIN.md                 # Entity model & relationships
│   ├── SETUP.md                  # Local dev setup guide
│   ├── PLAN.md                   # Phased migration plan
│   └── TODOS.md                  # Implementation checklist
│
└── tests/                        # (to be set up)
```

---

## API Surface

All routes are prefixed with `/api/v1`. No trailing slashes.

### Auth
| Method | Path                  | Description                            |
|--------|-----------------------|----------------------------------------|
| POST   | `/api/v1/auth/sync-user` | Upsert user record from Supabase token |

### Rooms
| Method | Path                              | Description                      |
|--------|-----------------------------------|----------------------------------|
| GET    | `/api/v1/rooms`                   | List rooms for current user      |
| POST   | `/api/v1/rooms`                   | Create a new room                |
| GET    | `/api/v1/rooms/{room_id}`         | Room home summary                |
| GET    | `/api/v1/rooms/{room_id}/dashboard` | Full member stats dashboard    |
| DELETE | `/api/v1/rooms/{room_id}`         | Delete room (Admin, all settled) |

### Expenses
| Method | Path                                              | Description                       |
|--------|---------------------------------------------------|-----------------------------------|
| GET    | `/api/v1/rooms/{room_id}/expenses`                | Paginated expenses (cursor-based) |
| POST   | `/api/v1/rooms/{room_id}/expenses`                | Add expense for self              |
| POST   | `/api/v1/rooms/{room_id}/expenses/for-member`     | Add expense for another (Admin)   |

### Splits
| Method | Path                                         | Description                         |
|--------|----------------------------------------------|-------------------------------------|
| GET    | `/api/v1/rooms/{room_id}/splits`             | Splits data (expenses + balances)   |
| POST   | `/api/v1/rooms/{room_id}/splits/settle`      | Settle one member's pending (Admin) |
| POST   | `/api/v1/rooms/{room_id}/splits/settle-all`  | Settle all pending members (Admin)  |

### Members
| Method | Path                                                    | Description              |
|--------|---------------------------------------------------------|--------------------------|
| GET    | `/api/v1/rooms/{room_id}/members`                       | List members             |
| GET    | `/api/v1/rooms/{room_id}/members/{member_id}`           | Member detail + summary  |
| PATCH  | `/api/v1/rooms/{room_id}/members/{member_id}/role`      | Update role (Admin)      |
| DELETE | `/api/v1/rooms/{room_id}/members/{member_id}`           | Remove member (Admin)    |
| DELETE | `/api/v1/rooms/{room_id}/members/me`                    | Exit room (non-admin)    |
| POST   | `/api/v1/rooms/{room_id}/members/{member_id}/settle`    | Settle member (legacy)   |
| POST   | `/api/v1/rooms/{room_id}/members/{member_id}/contribute`| Record contribution      |

### Invites
| Method | Path                                | Description                     |
|--------|-------------------------------------|---------------------------------|
| POST   | `/api/v1/rooms/{room_id}/invites`   | Create invite link (Admin)      |
| GET    | `/api/v1/invites/{token}`           | Validate invite token           |
| POST   | `/api/v1/invites/{token}/accept`    | Accept invite (join room)       |
| POST   | `/api/v1/invites/{token}/reject`    | Reject invite                   |

### Notifications
| Method | Path                                               | Description                         |
|--------|----------------------------------------------------|-------------------------------------|
| POST   | `/api/v1/notifications`                            | Create notification + send push     |
| GET    | `/api/v1/rooms/{room_id}/notifications`            | List room notifications             |
| POST   | `/api/v1/rooms/{room_id}/push-subscriptions`       | Register push subscription          |
| DELETE | `/api/v1/rooms/{room_id}/push-subscriptions`       | Unregister push subscription        |

---

## Authentication Flow

1. Client authenticates with Supabase Auth (Google OAuth or email/password).
2. Client receives a **Supabase JWT access token**.
3. Client sends `Authorization: Bearer <token>` on every request.
4. FastAPI dependency `get_current_user` verifies the JWT against Supabase's JWKS endpoint and extracts `sub` (uid) and `email`.
5. The user record in the `Users` table is looked up by email. If it doesn't exist (first login), the `/auth/sync-user` endpoint upserts it.

See `AUTH.md` for full details.

---

## CORS

Allow origins:
- `https://roomgrub.app` (web prod)
- `http://localhost:3000` (web dev)
- Android app (all origins when using capacitor / native HTTP, or specific origin for WebView)

---

## Key Design Decisions

- **Supabase stays as the DB** — no data migration required. Raw SQL maps to the existing schema.
- **Supabase Auth stays** — JWT tokens issued by Supabase are verified in FastAPI using the Supabase JWT secret. No custom auth server needed.
- **Raw SQL only** — all queries are parameterized SQL strings in `app/models/`. No SQLAlchemy ORM model classes. SQLAlchemy engine is used only for connection pooling via `db/engine.py`.
- **Sync SQLAlchemy** — using synchronous SQLAlchemy sessions. No async DB layer.
- **Business logic in services** — routers are thin; all rules (role checks, pending calculation, settle logic) live in service functions.
- **Push notifications via pywebpush** — same VAPID keys, same protocol, just Python implementation.
