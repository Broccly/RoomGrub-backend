# RoomGrub Backend — TODO Checklist

Open work first, shipped work below for reference. See [PLAN.md](PLAN.md) for the bigger picture and [CHANGELOG.md](../CHANGELOG.md) for what landed when.

## Open

### Code vs. convention
- [ ] **Services raise `HTTPException`.** The rule (AGENTS.md) is: routers and dependencies raise `HTTPException`; services raise plain exceptions that routers convert. Today `rooms`, `expenses`, `members`, `splits` and `invites` services — and `app/utils/auth_providers.py` — raise `HTTPException` directly (`members_services.exit_room` / `remove_member` and the `expenses_services` create, edit and delete paths are already converted; `get_expense_detail` is not). Refactor to plain exceptions (`ValueError` → 400, `PermissionError` → 403, a not-found error → 404, invite gone → 410) with the conversion in each router, keeping status codes and messages unchanged so the e2e tests still pass.
- [ ] `expenses_model.get_expenses` and `update_expense` assemble their `WHERE` / `SET` clauses with f-strings. Values are bound and the fragments are static, so it is not injectable, but it breaks the "no f-string SQL" rule — rewrite as static parameterized queries, as was done for the splits filters in 1.0.0.

### Stale artifacts
- [x] `db/schema.sql` is current up to migration `20261005120000`, but it is dumped from the Supabase project, so it carries the `auth` / `storage` / `realtime` schemas and legacy `Rooms` / `Users` columns that the migrations never create. Dump it from a database built purely from `db/migrations/`.
- [ ] `tests/e2e/test_notifications.py` still exercises the deleted `/rooms/{room_id}/push-subscriptions` routes and the unmounted notifications router. Rewrite it against `POST` / `DELETE /api/v1/notifications/fcm-token`.
- [ ] Drop `alembic` from `requirements.txt` and `pyproject.toml` — migrations are dbmate.
- [ ] `pytest` is not declared in `requirements.txt` or `pyproject.toml`, so a fresh virtualenv needs a manual `pip install pytest` (CONTRIBUTING.md says so). Add it as a dev dependency.
- [ ] Review the remaining permissive Supabase RLS policies (insert/select/update for `anon`/`authenticated` on `Users`, `Rooms`, `Spendings`, `Invite`, `notifications`). The backend bypasses RLS, so they only matter for direct Supabase-key access, which no client uses any more. `admin_can_delete` / `admin_can_update` on `Spendings` were dropped in `20261030120000`.
- [ ] Drop the unused `SpendingParticipants` table (created by the baseline migration, superseded by `SpendingSplits`).
- [ ] Tag releases in git (`v1.0.0`, `v1.1.0`, `v1.2.0`) to match CHANGELOG.md.

### Behaviour to verify or fix
- [ ] If the payer is not in `participant_user_ids` on **create**, no split row records `amount_paid`, so the balances for that expense don't net to zero. Edits already require the payer to stay in the split; decide whether creation should too.
- [ ] Share rounding: `round(money / n, 2)` per participant can leave a cent of drift per expense. Assign the remainder to one participant so splits always sum to `money`.
- [ ] `Spendings.money` is `bigint` while the API accepts fractional amounts and splits are `numeric(10,2)` — confirm whether fractional expenses are meant to be supported and align the column.
- [ ] `auth:user:{id}` is never invalidated, so a name/avatar refreshed at login stays stale in `current_user` for up to 7 days. Call `invalidate_cached_user` from `auth_services.login` (the helper exists and is unused). Folded into Guest access Phase B below.
- [ ] Settle-all only verifies the members the client sends. Decide whether to require every member with a non-zero balance.
- [ ] Events are published before the request's transaction commits; a later rollback would leave a `welcome` / `expense_split` event for something that didn't happen.

### Guest access & growth (PLAN.md Phase 12)
Design, rules and open decisions: [GUEST_ACCESS.md](GUEST_ACCESS.md). Build the phases in order; each one needs a dbmate migration where noted, e2e tests, the matching doc updates (move rules from GUEST_ACCESS.md into DOMAIN / AUTH / ARCHITECTURE) and a CHANGELOG entry.

**Before Phase B onwards:** settle open decisions 2–5 in GUEST_ACCESS.md.

**A — Remove the email dependency** — done (migration `20261030120000`); see the Done section below. Still to do: apply the migration to Supabase dev (backup first), then regenerate `db/schema.sql`.

**B — Room names and profile edits**
- [ ] `POST /rooms` with optional `{name}`; `name` in all room responses; `PATCH /rooms/{room_id}` (Admin)
- [ ] New `users` domain: `GET` / `PATCH /users/me` (`name`, `avatar`); invalidate `auth:user:{id}`
- [ ] `upsert_user` fills `name` / `profile` only when empty; login invalidates `auth:user:{id}` (behaviour change → CHANGELOG)

**C — Guest sign-up**
- [ ] `POST /auth/guest` → `type = 'guest'`, normal token pair, no `welcome` event; `type` on `get_current_user` and its cache
- [ ] Per-IP rate limit (Redis, fail-open) on `/auth/guest`

**D — Friends added by name**
- [ ] Migration: `Users.created_by`
- [ ] `POST /rooms/{room_id}/members/guests` (Admin) → `placeholder` user and `Member` row
- [ ] Placeholder can't be promoted to Admin; `PATCH /rooms/{room_id}/members/{user_id}` renames placeholders only
- [ ] Removing a placeholder deletes its `Users` row; room delete deletes the room's placeholders
- [ ] `type` / `is_guest` on member responses
- [ ] Check old Android / web builds for `null`-email crashes first (open decision 3)

**E — Public room link**
- [ ] Migration: `room_share_links` (one active link per room)
- [ ] `GET` (Member) / `POST` (Admin, create or rotate) / `DELETE` (Admin) `/rooms/{room_id}/share-link`
- [ ] Public `GET /join/{token}` preview including claimable placeholders
- [ ] `POST /join/{token}` with optional `claim_user_id` → idempotent join, placeholder claim through the merge service

**F — Guest signs in later**
- [ ] `users_services.merge_user_into` (lock order, same-room conflict → 409, repoint every FK, revoke source tokens, cache invalidation); also used by E
- [ ] `POST /auth/link`: upgrade in place when the email is new, otherwise merge into the existing account

### Features not built yet
- [ ] `POST /api/v1/auth/logout-all` — sign out every device of a user (revoke all their refresh-token families).
- [ ] A per-device label on `refresh_tokens` rows so a user can see and end individual sessions.
- [ ] Scheduled cleanup of `refresh_tokens`: dead rows are only deleted when their user logs in again, so rows of users who never return stay until the user is deleted.
- [ ] Settlement-history endpoint — list a member's closed `RoomBalanceSummary` rows, most recent first. The data is already being recorded.
- [ ] Activity log: decide whether to mount `notifications_router` (currently commented out in `main.py`) and have expense / member / settle actions write to it, or delete the router, service, model and table.
- [ ] Push for more than "expense added": settle-all, member joined, member removed.
- [ ] `GET /health` does not touch the DB — add a readiness check that does.
- [ ] Move CORS origins from `main.py` to an env var.
- [ ] Prod environment: `PROD_DB_*` vars, `prod_database_url` in `scripts/db_url.sh` (see MIGRATIONS.md).

### Clients
- [x] Web (Next.js): replace remaining Server Actions with calls to this API; send the RoomGrub JWT.
- [x] Web (Next.js): keep the refresh token in an httpOnly cookie owned by the Next.js server, refresh on `401 Token expired`, single-flight the refresh, sign out only when `/auth/refresh` returns 401.
- [x] Android: register / unregister the FCM token around login / logout; handle `expense_added` push payloads.
- [x] Android: store the refresh token in Keystore-backed storage, refresh on `401 Token expired` and retry once, single-flight the refresh, call `/auth/logout` on logout, sign out only when `/auth/refresh` returns 401.
- [ ] Email consumer for the `rg:emails` stream lives outside this repo — document its contract there and link it from ARCHITECTURE.md.

---

## Done

### Project setup
- [x] `pyproject.toml`, `requirements.txt`, `.env.example`
- [x] `db/config.py` — per-variable env getters, `validate_env()` on first DB use
- [x] `db/engine.py` — lazy sync SQLAlchemy engine + `db_conn()`
- [x] `app/api/`, `app/models/`, `app/services/`, `app/dependencies/` structure, all routers registered in `main.py`
- [x] `GET /health`
- [x] Local Docker Postgres for dev and test, dbmate migrations, migrate scripts
- [x] Vercel deployment config

### Auth
- [x] `POST /api/v1/auth/login` — Google `id_token` / Facebook token → RoomGrub JWT, user upsert
- [x] `get_current_user`, `require_room_member`, `require_room_admin`, `require_room_non_admin`
- [x] Redis cache-aside for user and room-access lookups, fail-open + circuit breaker
- [x] Access + refresh tokens: 15-minute access JWT, rotating hashed refresh tokens in `refresh_tokens`, sliding 90-day idle window, 30-second grace window, reuse detection per device
- [x] `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`

### Rooms
- [x] `GET /api/v1/rooms`, `POST /api/v1/rooms`
- [x] `GET /api/v1/rooms/{room_id}` — summary
- [x] `GET /api/v1/rooms/{room_id}/dashboard`
- [x] `DELETE /api/v1/rooms/{room_id}` — Admin, unsettled-expense guard, cascade

### Expenses
- [x] `GET /api/v1/rooms/{room_id}/expenses` — cursor pagination + filters
- [x] `POST /api/v1/rooms/{room_id}/expenses` — with optional `participant_user_ids`
- [x] `POST /api/v1/rooms/{room_id}/expenses/for-member` — Admin
- [x] `GET /api/v1/rooms/{room_id}/expenses/{expense_id}` — detail with participants
- [x] `PATCH` / `DELETE /api/v1/rooms/{room_id}/expenses/{expense_id}` — Admin
- [x] Settled expenses can't be edited or deleted (409), so their splits are never reversed against a later balance
- [x] `PATCH` can change an expense's participants (`participant_user_ids`)

### Split domain
- [x] `SpendingSplits` and `RoomBalanceSummary` tables, backfill and backfill fixes
- [x] `Spendings.user_id`, `Spendings.settled_at`; `balance` table dropped
- [x] Splits and active balances written on expense add / edit / delete, in the same transaction
- [x] `GET /api/v1/rooms/{room_id}/splits` reads active `RoomBalanceSummary` rows; suggested settlements via greedy debt simplification; `total_pending`
- [x] `POST /api/v1/rooms/{room_id}/splits/settle-all` — server-side verification (0.01 tolerance), close and reopen balance rows
- [x] Removed: contribute, single-member settle, filtered settle

Designed but deliberately not built: the `WRITE_PRECOMPUTED_SPLITS` feature flag and shadow-mode comparison (the cutover was done directly), and a Redis `splits_cache` (reads go straight to `RoomBalanceSummary`).

### Members
- [x] `GET /api/v1/rooms/{room_id}/members`, `GET .../members/{user_id}`
- [x] `PATCH .../members/{user_id}/role` — Admin, no self-demotion
- [x] `DELETE .../members/{user_id}` — Admin, not self, no-unsettled-expenses guard
- [x] `DELETE .../members/me` — non-admin, no-unsettled-expenses guard

### Guest access — Phase A
- [x] Migration `20261030120000`: `Users.type`, nullable `Users.email` (`''` → `NULL`), dropped `Users_profile_key`, stable UUID `uid` on `Users` and `Rooms`, `Rooms.name` everywhere, nullable `Spendings."user"`; legacy `Rooms.members` / `budget` / `admin`, `Users.role` and two RLS policies dropped
- [x] Payer lookups by `Spendings.user_id` (expenses, member detail, dashboard, splits); `user_id` expense filter
- [x] Settle-all accepts `user_id` or `user_email`
- [x] `admin_user_id` / `admin_name` on room responses; JWT `email` claim optional; email fields nullable

### Invites
- [x] `POST /api/v1/rooms/{room_id}/invites` — Admin
- [x] `GET /api/v1/invites/{token}` — public, returns inviter and `days_left`
- [x] `POST /api/v1/invites/{token}/accept` — idempotent
- [x] `POST /api/v1/invites/{token}/reject`

### Events and push
- [x] `app/events/publisher.py` — Redis stream `rg:emails`
- [x] `welcome` event on first login, `expense_split` event on settle-all
- [x] `fcm_tokens` table, `POST` / `DELETE /api/v1/notifications/fcm-token`
- [x] `push_service.send_push` — best-effort, savepoints, dead-token pruning
- [x] Push to participants on expense added

### Tests
- [x] `tests/e2e/` — auth, rooms, expenses, members, splits, invites (transaction-per-test against the test-db container, in-memory fake Redis)
- [x] `tests/unit/` — `test_auth_providers.py`, `test_push_service.py`
