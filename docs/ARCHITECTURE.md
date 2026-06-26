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
            │  │  DB (SQLAlchemy │  │
            │  │  + Supabase PG) │  │
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
| ORM           | SQLAlchemy 2.x (async)              | Maps existing schema, supports Postgres well |
| DB            | Supabase PostgreSQL (existing)      | No migration needed for schema               |
| Auth          | Supabase JWT verification           | Reuse existing Supabase Auth                 |
| Push Notifs   | `pywebpush`                         | Web Push Protocol, replaces `web-push` npm   |
| Validation    | Pydantic v2                         | Built into FastAPI, replaces manual checks   |
| Config        | `pydantic-settings` + `.env`        | 12-factor                                    |
| Tests         | `pytest` + `pytest-asyncio`         | Async test support                           |
| Migrations    | Alembic (if schema changes needed)  | Schema already exists in Supabase            |

---

## Project Structure

```
roomgrub-backend/
├── app/
│   ├── main.py                  # FastAPI app factory, CORS, lifespan
│   ├── config.py                # Settings (env vars via pydantic-settings)
│   ├── database.py              # Async SQLAlchemy engine + session factory
│   │
│   ├── models/                  # SQLAlchemy ORM models
│   │   ├── user.py
│   │   ├── room.py
│   │   ├── user_room.py
│   │   ├── spendings.py
│   │   ├── balance.py
│   │   ├── invite.py
│   │   ├── notification.py
│   │   └── push_subscription.py
│   │
│   ├── schemas/                 # Pydantic request/response models
│   │   ├── auth.py
│   │   ├── room.py
│   │   ├── expense.py
│   │   ├── member.py
│   │   ├── invite.py
│   │   ├── notification.py
│   │   └── split.py
│   │
│   ├── routers/                 # Route handlers (thin controllers)
│   │   ├── auth.py              # POST /auth/sync-user
│   │   ├── rooms.py             # CRUD for rooms + dashboard
│   │   ├── expenses.py          # Add/list expenses
│   │   ├── splits.py            # Splits view + settle
│   │   ├── members.py           # Manage members
│   │   ├── invites.py           # Invite link flow
│   │   └── notifications.py    # Push subscriptions + notification history
│   │
│   ├── services/                # Business logic, no HTTP concerns
│   │   ├── room_service.py
│   │   ├── expense_service.py
│   │   ├── split_service.py
│   │   ├── member_service.py
│   │   ├── invite_service.py
│   │   └── notification_service.py
│   │
│   ├── dependencies/
│   │   ├── auth.py              # get_current_user — JWT verify via Supabase
│   │   └── room_access.py       # Reusable guards: is_room_member, is_admin
│   │
│   └── utils/
│       ├── push.py              # Web Push helper (pywebpush)
│       └── pagination.py        # Cursor-based pagination helpers
│
├── tests/
│   ├── conftest.py
│   ├── test_rooms.py
│   ├── test_expenses.py
│   ├── test_splits.py
│   ├── test_members.py
│   └── test_invites.py
│
├── .env.example
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## API Surface

### Auth
| Method | Path                  | Description                            |
|--------|-----------------------|----------------------------------------|
| POST   | `/auth/sync-user`     | Upsert user record from Supabase token |

### Rooms
| Method | Path                        | Description                      |
|--------|-----------------------------|----------------------------------|
| GET    | `/rooms`                    | List rooms for current user      |
| POST   | `/rooms`                    | Create a new room                |
| GET    | `/rooms/{room_id}`          | Room home summary                |
| GET    | `/rooms/{room_id}/dashboard`| Full member stats dashboard      |
| DELETE | `/rooms/{room_id}`          | Delete room (Admin, all settled) |

### Expenses
| Method | Path                                        | Description                         |
|--------|---------------------------------------------|-------------------------------------|
| GET    | `/rooms/{room_id}/expenses`                 | Paginated expenses (cursor-based)   |
| POST   | `/rooms/{room_id}/expenses`                 | Add expense for self                |
| POST   | `/rooms/{room_id}/expenses/for-member`      | Add expense for another (Admin)     |

### Splits
| Method | Path                                   | Description                          |
|--------|----------------------------------------|--------------------------------------|
| GET    | `/rooms/{room_id}/splits`              | Splits data (expenses + balances)    |
| POST   | `/rooms/{room_id}/splits/settle`       | Settle one member's pending (Admin)  |
| POST   | `/rooms/{room_id}/splits/settle-all`   | Settle all pending members (Admin)   |

### Members
| Method | Path                                            | Description              |
|--------|-------------------------------------------------|--------------------------|
| GET    | `/rooms/{room_id}/members`                      | List members             |
| GET    | `/rooms/{room_id}/members/{member_id}`          | Member detail + summary  |
| PATCH  | `/rooms/{room_id}/members/{member_id}/role`     | Update role (Admin)      |
| DELETE | `/rooms/{room_id}/members/{member_id}`          | Remove member (Admin)    |
| DELETE | `/rooms/{room_id}/members/me`                   | Exit room (non-admin)    |
| POST   | `/rooms/{room_id}/members/{member_id}/settle`   | Settle member (legacy)   |
| POST   | `/rooms/{room_id}/members/{member_id}/contribute` | Record contribution    |

### Invites
| Method | Path                            | Description                     |
|--------|---------------------------------|---------------------------------|
| POST   | `/rooms/{room_id}/invites`      | Create invite link (Admin)      |
| GET    | `/invites/{token}`              | Validate invite token           |
| POST   | `/invites/{token}/accept`       | Accept invite (join room)       |
| POST   | `/invites/{token}/reject`       | Reject invite                   |

### Notifications
| Method | Path                                         | Description                          |
|--------|----------------------------------------------|--------------------------------------|
| POST   | `/notifications`                             | Create notification + send push      |
| GET    | `/rooms/{room_id}/notifications`             | List room notifications              |
| POST   | `/rooms/{room_id}/push-subscriptions`        | Register push subscription           |
| DELETE | `/rooms/{room_id}/push-subscriptions`        | Unregister push subscription         |

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

- **Supabase stays as the DB** — no data migration required. SQLAlchemy maps to the existing schema.
- **Supabase Auth stays** — JWT tokens issued by Supabase are verified in FastAPI using the Supabase JWT secret. No custom auth server needed.
- **No Supabase client library in Python** — direct SQLAlchemy queries replace the Supabase JS client. This removes the tight Supabase SDK coupling while keeping the DB.
- **Business logic in services** — routers are thin; all rules (role checks, pending calculation, settle logic) live in service classes.
- **Push notifications via pywebpush** — same VAPID keys, same protocol, just Python implementation.
