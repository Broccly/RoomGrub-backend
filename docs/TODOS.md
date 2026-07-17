# RoomGrub Backend — TODO Checklist

## Project Setup
- [x] Create `pyproject.toml` with project metadata
- [x] Create `requirements.txt` with pinned dependencies
- [x] Create `.env.example` with all required env vars documented
- [x] Create `db/config.py` — per-variable env getter functions
- [x] Create `db/engine.py` — sync SQLAlchemy engine + `db_conn()` session generator
- [x] Scaffold `app/api/`, `app/models/`, `app/services/`, `app/dependencies/` folder structure
- [x] Fix `main.py` — router registration is currently broken (imports routers as functions, not router objects)
- [x] `GET /api/v1/health` — simple endpoint to confirm DB connectivity
- [x] Set up `pytest` with a test DB session fixture and test client in `tests/conftest.py`

## Pydantic Schemas
Each domain's schemas live in `app/api/<domain>/schemas.py`:
- [x] `app/api/auth/schemas.py` — UserSyncRequest, UserResponse
- [x] `app/api/rooms/schemas.py` — RoomCreate, RoomResponse, RoomSummary, MemberStat, DashboardResponse
- [x] `app/api/expenses/schemas.py` — ExpenseCreate, ExpenseForMemberCreate, ExpenseResponse, PaginatedExpensesResponse
- [x] `app/api/members/schemas.py` — MemberResponse, MemberDetail, RoleUpdate
- [x] `app/api/splits/schemas.py` — SplitsData, SettleRequest, SettleAllRequest, MemberBalance
- [x] `app/api/invites/schemas.py` — InviteCreate, InviteValidation, InviteResponse
- [x] `app/api/notifications/schemas.py` — NotificationCreate, PushSubscriptionUpsert

## Dependencies
- [x] `app/dependencies/current_user.py` — `get_current_user` (JWT verify + DB lookup)
- [x] `app/dependencies/room_access.py` — `require_room_member`, `require_room_admin`

## Routers & Services

### Auth
- [x] `POST /api/v1/auth/sync-user` — upsert user from JWT claims
  - Router: `app/api/auth/api.py`
  - Service: `app/services/auth/auth_services.py`
  - Model: `app/models/auth/auth_model.py`

### Rooms
- [x] `GET /api/v1/rooms` — list rooms for current user
- [x] `POST /api/v1/rooms` — create room (atomic: create Room + add creator as Admin in UserRooms)
- [x] `GET /api/v1/rooms/{room_id}` — home summary (total purchases, pending, recent 5 expenses)
- [x] `GET /api/v1/rooms/{room_id}/dashboard` — member stats (purchases, pending per member)
- [x] `DELETE /api/v1/rooms/{room_id}` — delete room (Admin, 0 unsettled guard, cascade delete)
  - Router: `app/api/rooms/api.py`
  - Service: `app/services/rooms/rooms_services.py`
  - Model: `app/models/rooms/rooms_model.py`

### Expenses
- [x] `GET /api/v1/rooms/{room_id}/expenses` — paginated, cursor-based, with filters (settled, text, user, dateFrom, dateTo)
- [x] `POST /api/v1/rooms/{room_id}/expenses` — add expense for self
- [x] `POST /api/v1/rooms/{room_id}/expenses/for-member` — add for another member (Admin)
  - Router: `app/api/expenses/api.py`
  - Service: `app/services/expenses/expenses_services.py`
  - Model: `app/models/expenses/expenses_model.py`

### Members
- [x] `GET /api/v1/rooms/{room_id}/members` — list with roles
- [x] `GET /api/v1/rooms/{room_id}/members/{member_id}` — detail + pending + purchase history
- [x] `PATCH /api/v1/rooms/{room_id}/members/{member_id}/role` — update role (Admin, can't demote self)
- [x] `DELETE /api/v1/rooms/{room_id}/members/{member_id}` — remove (Admin, not self)
- [x] `DELETE /api/v1/rooms/{room_id}/members/me` — exit room (non-admin only)
- [x] `POST /api/v1/rooms/{room_id}/members/{member_id}/settle` — legacy lump-sum settle
- [x] `POST /api/v1/rooms/{room_id}/members/{member_id}/contribute` — record contribution
  - Router: `app/api/members/api.py`
  - Service: `app/services/members/members_services.py`
  - Model: `app/models/members/members_model.py`

### Splits
- [x] `GET /api/v1/rooms/{room_id}/splits` — unsettled expenses + lump-sum debits + members
- [x] `POST /api/v1/rooms/{room_id}/splits/settle` — settle one member (Admin)
- [x] `POST /api/v1/rooms/{room_id}/splits/settle-all` — settle all with server-side amount verification (Admin)
  - Router: `app/api/splits/api.py`
  - Service: `app/services/splits/splits_services.py`
  - Model: `app/models/splits/splits_model.py`

### Invites
- [x] `POST /api/v1/rooms/{room_id}/invites` — create invite link (Admin, generates UUID token)
- [x] `GET /api/v1/invites/{token}` — validate token (returns room info, daysLeft, invitedBy)
- [x] `POST /api/v1/invites/{token}/accept` — join room (idempotent, increments Room.members)
- [x] `POST /api/v1/invites/{token}/reject` — mark invite rejected
  - Router: `app/api/invites/api.py`
  - Service: `app/services/invites/invites_services.py`
  - Model: `app/models/invites/invites_model.py`

## Business Logic Checks (must implement in services)
- [x] Settle-all: server-side re-verification of pending amount per member (0.01 tolerance)
- [x] Room delete: block if any `Spendings.settled IS NOT TRUE` in the room
- [x] Invite accept: idempotent (already a member → return success without duplicate insert)
- [x] Role update: prevent self-demotion from Admin
- [x] Remove member: prevent self-removal by Admin (use `/members/me` to exit)
- [x] Exit room: only non-Admin can exit

## Tests
- [x] `tests/test_auth.py` — sync-user, JWT expired, JWT invalid
- [x] `tests/test_rooms.py` — create, list, summary, dashboard, delete (with settled/unsettled guard)
- [x] `tests/test_expenses.py` — add, paginated list, filters, for-member (admin guard)
- [x] `tests/test_members.py` — list, detail, role update, remove, exit
- [x] `tests/test_splits.py` — get splits, settle, settle-all (amount mismatch detection)
- [x] `tests/test_invites.py` — create, validate, accept (idempotent), reject, expired

## Redis Caching (done)
- [x] `db/redis_client.py` — Redis connection client
- [x] `db/redis_circuit.py` — circuit breaker (fail-open on Redis errors, 30s trip)
- [x] `app/cache/auth_cache.py` — cache-aside for `auth:user:{id}` and `access:{user_id}:{room_id}`, 7-day TTL, invalidated on membership/role writes

## Explicit Expense Participants + Precomputed Splits (new domain — see docs/domain-overview.html for a visual walkthrough)

Full design in the plan; PLAN.md/DOMAIN.md updated in lockstep. Not started yet — sequenced below.

### Phase 0 — Schema
- [ ] New migration `db/migrations/<ts>_add_spending_splits_and_balance_summary.sql`
- [ ] `SpendingSplits` table (spending_id, user_id, amount_paid, amount_owed) — merged participation + computed split; `net` is computed on read, not stored
- [ ] `RoomBalanceSummary` table (room_id, user_id, pending_amount, settled_at) — historical ledger; partial unique index `(room_id, user_id) WHERE settled_at IS NULL` allows only one active row per pair, closed rows persist as settlement history
- [ ] `Spendings.settled_at timestamptz NULL` (additive) — replaces the `LEFT JOIN balance` used today purely for settlement-timestamp display
- [ ] Update `app/models/rooms/rooms_model.py::delete_room_cascade` to remove `RoomBalanceSummary` rows

### Phase 1 — Backfill
- [ ] One-time backfill script/migration: populate `SpendingSplits` for existing `Spendings` (participants = current `UserRooms` members, even split)
- [ ] Backfill `Spendings.settled_at` from existing `balance.created_at` for already-settled expenses
- [ ] Populate one active `RoomBalanceSummary` row per (room, user) from backfilled splits + legacy `balance` adjustments (`spending_id IS NULL`)
- [ ] Spot-check backfilled active-row `pending_amount` against live `get_member_balances` output (within `TOLERANCE`)

### Phase 2 — Write path (shadow mode) + contribute removal
- [ ] `app/models/splits/splits_model.py` — `upsert_spending_splits`, `delete_spending_splits`, `get_active_room_balance`, `upsert_active_balance`, `close_and_reopen_balance`
- [ ] `app/services/splits/splits_write_services.py` (new) — `compute_and_write_splits`
- [ ] `app/api/expenses/schemas.py` — add optional `participant_user_ids: list[int] | None`
- [ ] `app/services/expenses/expenses_services.py` — write splits on add/edit/remove expense (same transaction); set `Spendings.settled_at` when settling
- [ ] Feature flag `WRITE_PRECOMPUTED_SPLITS` in `db/config.py`
- [ ] Shadow-mode logging: compare active `RoomBalanceSummary` row vs live `get_member_balances` on every settle check
- [ ] **Remove the "contribute" feature entirely** — no replacement: `POST /{room_id}/members/{user_id}/contribute` route (`app/api/members/api.py`), `ContributeRequest` schema, `members_services.record_contribution`, `members_model.insert_balance_credit`, and its tests in `tests/e2e/test_members.py`

### Phase 3 — Cache-aside reads + settlement close/reopen
- [ ] `app/cache/splits_cache.py` (new, mirrors `auth_cache.py`) — key `splits:room:{room_id}`, reuse `db/redis_circuit.py`
- [ ] Cut `GET /api/v1/rooms/{room_id}/splits` over to read the active `RoomBalanceSummary` row per member (cache-aside), compute pairwise pay-to/pay-from via greedy debt-simplification at read time
- [ ] Wire full settle (`settle_member_balance`/`settle_all_room`) to call `close_and_reopen_balance` (stamp `settled_at`, open a fresh zeroed active row) instead of writing to `balance`
- [ ] Wire partial/filtered settle (`settle_filtered_room`) to update the active row in place (not a close-out event)
- [ ] Add settlement-history read endpoint (closed `RoomBalanceSummary` rows for a member, most recent first)
- [ ] Cache invalidation on every balance-changing write

### Phase 4 — API surface
- [ ] `GET /api/v1/rooms/{room_id}/expenses/{expense_id}/participants`

### Phase 5 — Cutover, `balance` removal & deprecation
- [ ] Burn-in period with zero material shadow-mode discrepancies
- [ ] Remove `get_member_balances`, `get_pending_for_user`, `get_pending_for_user_filtered`, `get_filtered_unsettled_expenses`
- [ ] Rewire settle `TOLERANCE` check to compare against active `RoomBalanceSummary` row only
- [ ] Switch `expenses_model.py` / `rooms_model.py::get_recent_expenses` from `LEFT JOIN balance` to `Spendings.settled_at`
- [ ] Confirm zero remaining references to `balance` (grep), then drop the `balance` table in a final migration

## Documentation
- [x] `docs/DOMAIN.md` — entities, business rules, relationships
- [x] `docs/ARCHITECTURE.md` — system design, actual project structure, API surface
- [x] `docs/AUTH.md` — JWT verification, user sync, role guards
- [x] `docs/PLAN.md` — phased migration plan
- [x] `docs/TODOS.md` — this file
- [x] `docs/SETUP.md` — local dev setup guide
- [x] `README.md` — top-level overview
- [x] `CLAUDE.md` — agent instructions for Claude Code
- [x] `AGENTS.md` — architecture patterns and conventions for AI agents
