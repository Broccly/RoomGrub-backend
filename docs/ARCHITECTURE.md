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
            │   Routers             │        ┌──────────────────────┐
            │      │                │───────▶│ Google / Facebook    │
            │   Services            │        │ (login token verify) │
            │      │                │        └──────────────────────┘
            │   Models (raw SQL)    │        ┌──────────────────────┐
            │                       │───────▶│ Firebase Cloud       │
            └─────┬───────────┬─────┘        │ Messaging (push)     │
                  │           │              └──────────────────────┘
                  ▼           ▼
       ┌────────────────┐  ┌─────────────────────────────┐
       │ PostgreSQL     │  │ Redis (Upstash)             │
       │ (Supabase)     │  │  - auth / room-access cache │
       │                │  │  - rg:emails event stream ──┼──▶ email consumer
       └────────────────┘  └─────────────────────────────┘     (outside this repo)
```

---

## Tech Stack

| Layer         | Choice                              | Reason                                       |
|---------------|-------------------------------------|----------------------------------------------|
| Framework     | FastAPI                             | Fast, typed, auto-docs                       |
| DB Queries    | Raw SQL (parameterized)             | Full control, no ORM abstraction             |
| DB Connection | SQLAlchemy engine (sync)            | Connection pooling only — no ORM used        |
| DB            | PostgreSQL (Supabase-hosted; local Docker for dev/test) | Existing data stays where it is |
| Migrations    | [dbmate](https://github.com/amacneil/dbmate) | Plain versioned SQL files, same tool for every environment |
| Auth          | Google / Facebook token verification + app-issued HS256 access JWT (`PyJWT`, `google-auth`); rotating refresh tokens in Postgres | No dependency on Supabase Auth |
| Cache         | Redis (Upstash)                     | Cache-aside for auth/room-access reads, fail-open with circuit breaker |
| Events        | Redis stream (`rg:emails`)          | Decouples email sending from the request path |
| Push Notifs   | Firebase Cloud Messaging (`firebase-admin`) | One sender for the Android app          |
| Validation    | Pydantic v2                         | Request/response schemas and model-layer row validation |
| Config        | `.env` + per-var getter functions   | Simple, explicit, 12-factor                  |
| Tests         | `pytest`                            | e2e against a disposable Postgres, plus unit tests |
| Deployment    | Vercel (`@vercel/python`, `vercel.json`) | Serverless, zero infra                  |

> **No ORM.** SQLAlchemy is present only for the connection engine and pool (`db/engine.py`). All database interaction uses raw parameterized SQL strings in `app/models/`.

---

## Project Structure

```
RoomGrub-backend/
├── main.py                       # FastAPI app, CORS, router registration, /health
│
├── app/
│   ├── api/<domain>/             # Route handlers — one folder per domain
│   │   ├── api.py                #   Router + route functions
│   │   └── schemas.py            #   Pydantic request/response models
│   │
│   ├── services/<domain>/        # Business logic, no HTTP concerns
│   │   └── <domain>_services.py
│   │
│   ├── models/<domain>/          # Raw SQL query functions — no ORM model classes
│   │   ├── <domain>_model.py     #   One function per query
│   │   └── schemas.py            #   Pydantic row validators for query results
│   │
│   │   Domains: auth, rooms, expenses, members, splits, invites, notifications
│   │   Extra:   services/notifications/push_service.py — FCM sender
│   │
│   ├── dependencies/             # FastAPI dependency injection
│   │   ├── current_user.py       # get_current_user — verify the access JWT, load user
│   │   └── room_access.py        # require_room_member / _admin / _non_admin
│   │
│   ├── cache/
│   │   └── auth_cache.py         # Cache-aside helpers for auth/room-access (fail-open, circuit breaker)
│   │
│   ├── events/
│   │   └── publisher.py          # publish_event → Redis stream rg:emails
│   │
│   └── utils/
│       ├── auth_providers.py     # Google / Facebook token verification
│       └── jwt_utils.py          # create_jwt (access token), refresh-token generation and hashing
│
├── db/
│   ├── config.py                 # Per-variable env getter functions + validate_env()
│   ├── engine.py                 # SQLAlchemy sync engine + db_conn() session generator
│   ├── redis_client.py           # Redis client singleton + redis_conn() dependency
│   ├── redis_circuit.py          # In-process circuit breaker for Redis outages
│   ├── migrations/               # dbmate migrations (versioned .sql)
│   └── schema.sql                # dbmate schema dump
│
├── scripts/                      # db_url.sh, migrate_dev_db.sh, migrate_test_db.sh
├── docker-compose.yml            # dev-db and test-db Postgres containers
├── vercel.json                   # Vercel deployment config
│
├── docs/
│   ├── ARCHITECTURE.md           # This file
│   ├── AUTH.md                   # Login, access + refresh tokens, role guards
│   ├── DOMAIN.md                 # Entity model & business rules
│   ├── SETUP.md                  # Env vars and external services
│   ├── MIGRATIONS.md             # Writing and applying dbmate migrations
│   ├── PLAN.md                   # Project status and what's next
│   ├── TODOS.md                  # Open work
│   └── domain-overview.html      # Visual walkthrough of the expense/split model
│
└── tests/
    ├── e2e/                      # API tests against the test-db container
    └── unit/                     # Pure unit tests (auth providers, push service)
```

---

## API Surface

All routes are prefixed with `/api/v1`. No trailing slashes. "Member" / "Admin" in the tables below mean the caller's role in `{room_id}`.

### Auth
| Method | Path                  | Access | Description                                        |
|--------|-----------------------|--------|----------------------------------------------------|
| POST   | `/api/v1/auth/login`  | Public | Exchange a Google/Facebook token for a RoomGrub access token and refresh token; upserts the user |
| POST   | `/api/v1/auth/refresh` | Public | Trade a refresh token for a new access + refresh token pair (rotation) |
| POST   | `/api/v1/auth/logout`  | Public | Revoke the device's refresh tokens; 204 |

### Rooms
| Method | Path                                | Access | Description                                       |
|--------|-------------------------------------|--------|---------------------------------------------------|
| GET    | `/api/v1/rooms`                     | User   | List rooms for current user                       |
| POST   | `/api/v1/rooms`                     | User   | Create a room; creator becomes Admin              |
| GET    | `/api/v1/rooms/{room_id}`           | Member | Room summary: `total_spent`, `pending_amount`     |
| GET    | `/api/v1/rooms/{room_id}/dashboard` | Member | Room + per-member unsettled spend                 |
| DELETE | `/api/v1/rooms/{room_id}`           | Admin  | Delete room (blocked while unsettled expenses remain) |

### Expenses
| Method | Path                                              | Access | Description                               |
|--------|---------------------------------------------------|--------|-------------------------------------------|
| GET    | `/api/v1/rooms/{room_id}/expenses`                | Member | Paginated list (cursor-based). Filters: `settled`, `search`, `user_email`, `date_from`, `date_to` |
| POST   | `/api/v1/rooms/{room_id}/expenses`                | Member | Add expense paid by self; optional `participant_user_ids` |
| GET    | `/api/v1/rooms/{room_id}/expenses/{expense_id}`   | Member | Expense detail with payer and per-participant split |
| PATCH  | `/api/v1/rooms/{room_id}/expenses/{expense_id}`   | Admin  | Edit `material`, `money`, `created_at`    |
| DELETE | `/api/v1/rooms/{room_id}/expenses/{expense_id}`   | Admin  | Delete expense and reverse its splits     |
| POST   | `/api/v1/rooms/{room_id}/expenses/for-member`     | Admin  | Add expense paid by another member (`user_id`) |

### Splits
| Method | Path                                         | Access | Description                               |
|--------|----------------------------------------------|--------|-------------------------------------------|
| GET    | `/api/v1/rooms/{room_id}/splits`             | Member | Member balances, unsettled expenses, suggested settlements, `total_pending` |
| POST   | `/api/v1/rooms/{room_id}/splits/settle-all`  | Admin  | Settle the whole room after verifying client-sent balances |

### Members
| Method | Path                                                | Access    | Description                          |
|--------|-----------------------------------------------------|-----------|--------------------------------------|
| GET    | `/api/v1/rooms/{room_id}/members`                   | Member    | List members                         |
| GET    | `/api/v1/rooms/{room_id}/members/{user_id}`         | Member    | Member detail, totals, pending expenses |
| PATCH  | `/api/v1/rooms/{room_id}/members/{user_id}/role`    | Admin     | Change role                          |
| DELETE | `/api/v1/rooms/{room_id}/members/me`                | Non-admin | Exit room (blocked with outstanding balance) |
| DELETE | `/api/v1/rooms/{room_id}/members/{user_id}`         | Admin     | Remove member (blocked with outstanding balance) |

### Invites
| Method | Path                                | Access | Description                     |
|--------|-------------------------------------|--------|---------------------------------|
| POST   | `/api/v1/rooms/{room_id}/invites`   | Admin  | Create invite link              |
| GET    | `/api/v1/invites/{token}`           | Public | Validate invite token           |
| POST   | `/api/v1/invites/{token}/accept`    | User   | Accept invite (join room)       |
| POST   | `/api/v1/invites/{token}/reject`    | User   | Reject invite                   |

### Push
| Method | Path                               | Access | Description                               |
|--------|------------------------------------|--------|-------------------------------------------|
| POST   | `/api/v1/notifications/fcm-token`  | User   | Register this device's FCM token          |
| DELETE | `/api/v1/notifications/fcm-token`  | User   | Unregister this device's FCM token        |

### Notifications (activity log) — **not mounted**
The room-scoped activity-log router exists in `app/api/notifications/api.py` but is commented out in `main.py`, so these routes return 404 today.

| Method | Path                                      | Access | Description               |
|--------|-------------------------------------------|--------|---------------------------|
| POST   | `/api/v1/rooms/{room_id}/notifications`   | Member | Create activity log entry |
| GET    | `/api/v1/rooms/{room_id}/notifications`   | Member | List room activity        |

### Health
| Method | Path      | Access | Description                    |
|--------|-----------|--------|--------------------------------|
| GET    | `/health` | Public | Liveness check (no DB access)  |

---

## Authentication Flow

1. Client signs in with Google or Facebook and receives a provider token.
2. Client calls `POST /api/v1/auth/login` with `{provider, token}`.
3. The backend verifies the token with the provider, upserts the `Users` row, and returns a short-lived **access token** (HS256 JWT, signed with `JWT_SECRET`, `sub` = user id) and a long-lived **refresh token** (opaque, stored hashed in `refresh_tokens`).
4. Client sends `Authorization: Bearer <access_token>` on every other request.
5. `get_current_user` verifies the JWT and loads the user (Redis first, then Postgres). Room-scoped routes add `require_room_member` / `require_room_admin` / `require_room_non_admin`.
6. When the access token expires (`401 Token expired`), the client calls `POST /api/v1/auth/refresh` with its refresh token and gets a new pair. The old refresh token is spent; replaying it revokes that device's session.
7. `POST /api/v1/auth/logout` revokes the device's refresh tokens.

A device therefore stays signed in until the user logs out, it sits idle past `REFRESH_TOKEN_EXPIRY_DAYS`, or its refresh token is revoked.

See `AUTH.md` for full details.

---

## Caching Layer

Redis (hosted on Upstash) caches two hot, low-cardinality lookups using a cache-aside pattern:

- **Auth**: `get_current_user` (`app/dependencies/current_user.py`) checks `auth:user:{user_id}` before querying `Users`; on a miss it queries Postgres and populates the cache.
- **Room access**: `require_room_member` (`app/dependencies/room_access.py`) checks `access:{user_id}:{room_id}` before querying `UserRooms`; on a miss it queries Postgres and populates the cache.

Both keys carry a **7-day TTL** as a safety-net backstop, not the primary consistency mechanism — consistency for room access comes from **active invalidation on every write** that changes membership or role: room deletion, invite acceptance, role change, member removal, and self-exit (see the corresponding service functions in `app/services/rooms/`, `app/services/invites/`, `app/services/members/`, which call the `invalidate_*` helpers in `app/cache/auth_cache.py` after the underlying write). The `auth:user` key is not actively invalidated.

**Redis is never a dependency — only an optimization.** All cache operations are wrapped so a Redis outage degrades to "always miss" instead of failing requests:
- Every `get_cached_*`/`set_cached_*`/`invalidate_*` call catches `redis.RedisError` (and `ValueError` for corrupt JSON), logs a warning, and falls through to Postgres.
- A small in-process circuit breaker (`db/redis_circuit.py`) trips for 30 seconds after any Redis failure, so subsequent requests skip Redis entirely (no repeated connection timeouts) until the cooldown expires and one probe request retries it.
- Connection/socket timeouts are set to 1s so even that probe request fails fast if Redis is still down.

Balances are **not** cached in Redis — `GET /splits` reads the precomputed `RoomBalanceSummary` rows straight from Postgres.

---

## Events

`app/events/publisher.py` exposes one function:

```python
publish_event(client: redis.Redis, event_type: str, payload: dict) -> None
```

It appends `{"type": <event_type>, "payload": <json string>}` to the Redis stream **`rg:emails`** with `XADD`. A consumer outside this repo reads the stream and sends the emails. Publishing never raises — a failure is logged and the request carries on.

| Event type | Published when | Payload |
|------------|----------------|---------|
| `welcome` | A user logs in for the first time (`auth_services.login`, when `upsert_user` reports `inserted`) | `email`, `name` |
| `expense_split` | An admin settles a room (`splits_services.settle_all`) | `expense_title`, `total_pending`, `members[] {name, email, pending_amount}`, `settlements[] {from_name, to_name, amount}` — captured just before the balances are zeroed |

Events are published inside the request, before the DB transaction commits, and do not go through the cache circuit breaker.

---

## Push Notifications

Push goes through Firebase Cloud Messaging.

- **Tokens**: the app registers its device token with `POST /api/v1/notifications/fcm-token` (`{fcm_token, platform}`) and removes it with `DELETE` on logout. Tokens live in `fcm_tokens`, unique per token — if a different user logs in on the same device, the row is re-assigned to them.
- **Sending**: `send_push(conn, user_ids, title, body, data)` in `app/services/notifications/push_service.py` sends one message per registered device of the given users.
- **Best-effort**: `send_push` never raises. Its queries run in savepoints (`conn.begin_nested()`), so a failed statement cannot abort the caller's transaction and silently roll back the expense that triggered it.
- **Pruning**: tokens FCM reports as `Unregistered` or `SenderIdMismatch` are deleted.
- **Disabled when unconfigured**: if `FIREBASE_CREDENTIALS_JSON` is unset or invalid, Firebase is never initialised and sends are skipped with a warning.

| Trigger | Recipients | `data` |
|---------|------------|--------|
| Expense added (`POST /expenses`, `POST /expenses/for-member`) | Every participant in the split except whoever added it | `type=expense_added`, `room_id`, `expense_id` |

---

## CORS

Allowed origins (hard-coded in `main.py`):
- `https://roomgrub.app`
- `https://roomgrub.broccly.in`
- `http://localhost:3000`
- `http://localhost:3001`

The Android app uses native HTTP and is not subject to CORS.

---

## Key Design Decisions

- **Supabase is only the Postgres host** — no data migration was required, but Supabase Auth, RLS and client SDKs are not used. All access control is enforced in this service.
- **The backend issues its own tokens** — provider tokens (Google/Facebook) are verified once at login; every other request carries a RoomGrub access JWT.
- **Stateless access, stateful refresh** — access tokens are short-lived JWTs verified by signature alone; refresh tokens are opaque, single-use, stored hashed in Postgres and revocable. They are deliberately not in Redis, which is fail-open — an outage must not sign every device out.
- **Raw SQL only** — all queries are parameterized SQL strings in `app/models/`. No SQLAlchemy ORM model classes. SQLAlchemy engine is used only for connection pooling via `db/engine.py`.
- **Sync SQLAlchemy** — using synchronous connections. No async DB layer.
- **One transaction per request** — `db_conn()` commits on success and rolls back on error; code never commits manually.
- **Business logic in services** — routers are thin; all rules (role checks, split calculation, settle logic) live in service functions.
- **Balances are precomputed at write time** — every expense add/edit/delete updates `SpendingSplits` and the member's active `RoomBalanceSummary` row in the same transaction, so reads are a simple lookup.
- **Redis is a pure optimization, never a dependency** — cache failures are caught and logged; requests always fall back to Postgres, which remains the source of truth.
- **Side effects are best-effort** — event publishing and push sends never fail or roll back the request that triggered them.
