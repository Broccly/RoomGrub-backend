# RoomGrub Backend — Plan & Status

## Goal

Extract all backend logic from the tightly-coupled Next.js app (`/Broccly/RoomGrub`) into a standalone **Python FastAPI** service, so the RoomGrub web app and the Android app share one API.

**Status (2026-10-05, v1.2.0):** the API is feature-complete for rooms, expenses, splits, members and invites, and has been extended beyond the original monolith with explicit expense participants, precomputed balances, an event stream and FCM push. Refresh tokens (Phase 1b) are built and unreleased. What remains is hardening, the activity log decision, and finishing the client migrations.

This file tracks phases. The granular checklist is [TODOS.md](TODOS.md); dated detail is in [CHANGELOG.md](../CHANGELOG.md).

---

## How the plan changed

The original plan (June 2026) assumed Supabase Auth JWTs, async SQLAlchemy ORM models, Alembic and Web Push. What was built instead:

| Planned | Built | Why |
|---------|-------|-----|
| Verify Supabase Auth JWTs | Verify Google/Facebook tokens at login, issue our own JWT | No dependency on Supabase Auth; one flow for web and Android |
| Async SQLAlchemy ORM | Sync engine, raw parameterized SQL | Full control of queries, no ORM layer |
| Alembic | dbmate | Plain SQL migrations, same tool for every environment |
| Live pending calculation + `balance` ledger | `SpendingSplits` + `RoomBalanceSummary`, precomputed at write time | Explicit participants per expense; reads are a lookup; settlements keep history |
| Web Push (`pywebpush`, VAPID) | Firebase Cloud Messaging | The Android app is the push target |
| Notifications sent from a `/notifications` endpoint | Push sent by the service that performs the action; emails via a Redis event stream | Clients can't forge or forget notifications |

---

## Phases

### Phase 0 — Setup ✅ (0.0.1, June 2026)
FastAPI app, sync engine + `db_conn()`, env config, `/health`, pytest.

### Phase 1 — Auth ✅ (0.0.1 → 1.1.0)
`POST /auth/login`, `get_current_user`, room guards. Google `id_token` verification hardened in 1.1.0. Redis cache-aside for user and room-access lookups.

### Phase 1b — Refresh tokens ✅ (unreleased, October 2026)
Replaced the single 24-hour JWT with a 15-minute access token plus a rotating, revocable refresh token stored hashed in Postgres, so a signed-in device is never signed out just because a token expired. Sliding 90-day idle window, reuse detection per device, `POST /auth/refresh` and `POST /auth/logout`. Details in [AUTH.md](AUTH.md).

### Phase 2 — Rooms ✅
List, create, summary, dashboard, delete with unsettled guard.

### Phase 3 — Expenses ✅
Paginated list with filters, add, add for member, detail, edit, delete.

### Phase 4 — Members ✅
List, detail, role change, remove, exit. Legacy settle and contribute endpoints were built, then removed in 1.1.0.

### Phase 5 — Splits ✅ (reworked in 1.1.0, July 2026)
Replaced live aggregation and the `balance` table with `SpendingSplits` and `RoomBalanceSummary`. `GET /splits` with suggested settlements; settle-all with server-side verification and close/reopen history.

### Phase 6 — Invites ✅
Create, public validate, idempotent accept, reject, 7-day expiry.

### Phase 7 — Notifications & Push — partly done (1.2.0, September 2026)
- ✅ FCM token registration, `send_push`, push on expense added
- ✅ Event stream (`rg:emails`): `welcome`, `expense_split`
- ⬜ Activity log — router exists but is unmounted; mount it or remove it
- ⬜ Push for settle-all and membership changes

### Phase 8 — Testing & Hardening — in progress
- ✅ e2e suite against a disposable Postgres, unit tests for auth providers and push
- ⬜ Bring services in line with the error-handling convention (plain exceptions, routers convert)
- ⬜ Fix the stale notifications tests and regenerate `db/schema.sql`
- ⬜ Resolve the split edge cases listed in TODOS.md (settled-expense edits, payer outside participants, rounding)
- ⬜ Settlement-history endpoint

### Phase 9 — Web App Migration — tracked in the web repo
Update the `RoomGrub` Next.js app to call this API instead of Server Actions:
- ⬜ Replace all `'use server'` action files with `fetch()` calls
- ⬜ Log in via `POST /auth/login` and send the RoomGrub JWT
- ⬜ Refresh token in an httpOnly cookie on the Next.js server, silent refresh on 401
- ⬜ Remove `src/database/` and `src/services/NotificationService.js`

### Phase 10 — Android App Integration — tracked in the app repo
- ⬜ Google sign-in → `POST /auth/login`; store both tokens
- ⬜ Refresh on 401 and retry; back to sign-in only when `/auth/refresh` itself returns 401; call `/auth/logout` on logout
- ⬜ Register / unregister the FCM token around login / logout
- ⬜ Handle `expense_added` push payloads (`room_id`, `expense_id`)
- ⬜ Test all endpoints from the app

### Phase 11 — Production
- ⬜ Prod database, `PROD_DB_*` vars and migration path (MIGRATIONS.md)
- ⬜ CORS origins from config
- ⬜ Readiness check that touches the DB
- ⬜ Git tags per release

The boxes in Phases 9–10 list what this backend expects from the clients; their actual progress is not tracked here.

---

## Deployment

- Configured for Vercel via `vercel.json` (`@vercel/python`, all routes → `main.py`).
- Environment variables set in the Vercel project — see [SETUP.md](SETUP.md) for the full list.
- Postgres on Supabase, Redis on Upstash, push via Firebase.
- Schema changes go through dbmate migrations — see [MIGRATIONS.md](MIGRATIONS.md).
