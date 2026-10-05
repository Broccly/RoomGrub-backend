# RoomGrub Backend — TODO Checklist

Open work first, shipped work below for reference. See [PLAN.md](PLAN.md) for the bigger picture and [CHANGELOG.md](../CHANGELOG.md) for what landed when.

## Open

### Code vs. convention
- [ ] **Services raise `HTTPException`.** The rule (AGENTS.md) is: routers and dependencies raise `HTTPException`; services raise plain exceptions that routers convert. Today `rooms`, `expenses`, `members`, `splits` and `invites` services — and `app/utils/auth_providers.py` — raise `HTTPException` directly. Refactor to plain exceptions (`ValueError` → 400, `PermissionError` → 403, a not-found error → 404, invite gone → 410) with the conversion in each router, keeping status codes and messages unchanged so the e2e tests still pass.
- [ ] `expenses_model.get_expenses` and `update_expense` assemble their `WHERE` / `SET` clauses with f-strings. Values are bound and the fragments are static, so it is not injectable, but it breaks the "no f-string SQL" rule — rewrite as static parameterized queries, as was done for the splits filters in 1.0.0.

### Stale artifacts
- [ ] Regenerate `db/schema.sql`. It stops at migration `20260724130000` — it still has `push_subscriptions` and no `fcm_tokens` — and it was dumped from the Supabase project, so it carries the `auth` / `storage` / `realtime` schemas and legacy `Rooms` / `Users` columns that the migrations never create. Dump it from a database built purely from `db/migrations/`.
- [ ] `tests/e2e/test_notifications.py` still exercises the deleted `/rooms/{room_id}/push-subscriptions` routes and the unmounted notifications router. Rewrite it against `POST` / `DELETE /api/v1/notifications/fcm-token`.
- [ ] Drop `alembic` from `requirements.txt` and `pyproject.toml` — migrations are dbmate.
- [ ] `pytest` is not declared in `requirements.txt` or `pyproject.toml`, so the README's install-then-`pytest -v` steps fail on a fresh virtualenv. Add it as a dev dependency.
- [ ] Drop the unused `SpendingParticipants` table (created by the baseline migration, superseded by `SpendingSplits`).
- [ ] Tag releases in git (`v1.0.0`, `v1.1.0`, `v1.2.0`) to match CHANGELOG.md.

### Behaviour to verify or fix
- [ ] Editing or deleting an **already settled** expense reverses its splits against the member's *current* active balance. Either block edits/deletes of settled expenses or skip the balance reversal for them.
- [ ] If the payer is not in `participant_user_ids`, no split row records `amount_paid`: the balances for that expense don't net to zero, and a later `money` edit drops its splits entirely (`edit_expense` only re-applies when it finds a payer row). Decide whether the payer must always be a participant.
- [ ] Share rounding: `round(money / n, 2)` per participant can leave a cent of drift per expense. Assign the remainder to one participant so splits always sum to `money`.
- [ ] `Spendings.money` is `bigint` while the API accepts fractional amounts and splits are `numeric(10,2)` — confirm whether fractional expenses are meant to be supported and align the column.
- [ ] `auth:user:{id}` is never invalidated, so a name/avatar refreshed at login stays stale in `current_user` for up to 7 days. Call `invalidate_cached_user` from `auth_services.login` (the helper exists and is unused).
- [ ] Settle-all only verifies the members the client sends. Decide whether to require every member with a non-zero balance.
- [ ] Events are published before the request's transaction commits; a later rollback would leave a `welcome` / `expense_split` event for something that didn't happen.

### Features not built yet
- [ ] Settlement-history endpoint — list a member's closed `RoomBalanceSummary` rows, most recent first. The data is already being recorded.
- [ ] Activity log: decide whether to mount `notifications_router` (currently commented out in `main.py`) and have expense / member / settle actions write to it, or delete the router, service, model and table.
- [ ] Push for more than "expense added": settle-all, member joined, member removed.
- [ ] Changing an expense's participants after creation.
- [ ] `GET /health` does not touch the DB — add a readiness check that does.
- [ ] Move CORS origins from `main.py` to an env var.
- [ ] Prod environment: `PROD_DB_*` vars, `prod_database_url` in `scripts/db_url.sh` (see MIGRATIONS.md).

### Clients
- [ ] Web (Next.js): replace remaining Server Actions with calls to this API; send the RoomGrub JWT.
- [ ] Android: register / unregister the FCM token around login / logout; handle `expense_added` push payloads.
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
- [x] `DELETE .../members/{user_id}` — Admin, not self, zero-balance guard
- [x] `DELETE .../members/me` — non-admin, zero-balance guard

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
