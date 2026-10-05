# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [Unreleased]

## [1.2.0] - 2026-09-19
### Added

- Redis stream event publisher (`app/events/publisher.py`): `publish_event` appends `{type, payload}` entries to the `rg:emails` stream for an out-of-process consumer; publish failures are logged and never fail the request
- `welcome` event published on a user's first login (`POST /auth/login` → `auth_services.login`), detected via the new `inserted` flag returned by `upsert_user` (`app/models/auth/auth_model.py`, `app/models/auth/schemas.py`)
- `expense_split` event published on `POST /rooms/{room_id}/splits/settle-all`, carrying the settlement summary (`members`, `settlements`, `total_pending`) as it stood just before settling (`app/services/splits/splits_services.py`)
- `total_pending` field on `GET /rooms/{room_id}/splits` — sum of all unsettled expenses in the room (`app/api/splits/schemas.py`, `app/models/splits/splits_model.py::get_total_pending_amount`)
- FCM push notifications: `fcm_tokens` table (one row per device token; a token is re-assigned when another user logs in on the same device) with `POST` / `DELETE /api/v1/notifications/fcm-token` for the app to register and unregister its device token (`app/api/notifications/api.py::push_router`, migration `20260903083333`)
- `push_service.send_push` (`app/services/notifications/push_service.py`): best-effort send via `firebase-admin`, prunes tokens FCM reports as unregistered, never raises, and runs its queries in savepoints so a failure can't roll back the caller's transaction
- Push to an expense's participants (everyone in the split except whoever added it) on add expense and add expense for member
- `FIREBASE_CREDENTIALS_JSON` env var (optional — push is disabled when unset)
- Unit test suite under `tests/unit/` (`test_push_service.py`, alongside the existing `test_auth_providers.py`)

### Changed

- `POST /auth/login` and `POST /rooms/{room_id}/splits/settle-all` now depend on `redis_conn` in order to publish events
- App version is now declared consistently as `1.2.0` in `pyproject.toml`, `uv.lock` and `main.py` (previously `0.0.1` / `0.1.0`)

### Removed

- `push_subscriptions` table and the VAPID / Web Push `POST` / `DELETE /rooms/{room_id}/push-subscriptions` routes, replaced by FCM tokens
- Stale `push_subscriptions` delete from `delete_room_cascade` (`app/models/rooms/rooms_model.py`)

## [1.1.0] - 2026-08-01
### Added

- Redis (Upstash) cache-aside layer for auth (`get_current_user`) and room-membership checks (`require_room_member`), with active invalidation on room delete, invite accept, role change, and member remove/exit (`app/cache/auth_cache.py`, `db/redis_client.py`, dependency/service wiring)
- Fail-open Redis handling: cache read/write/invalidate errors are caught and logged as warnings, falling back to Postgres instead of failing the request
- In-process circuit breaker (`db/redis_circuit.py`) that skips Redis entirely for 30s after a failure, so a Redis outage doesn't add per-request timeout latency
- Split domain: `SpendingSplits` (one row per participant per expense, `amount_paid` / `amount_owed`) and `RoomBalanceSummary` (one active row per member per room plus closed rows from past settle-alls), written in the same transaction as every expense add/edit/delete (migration `20260722120000`, `app/models/expenses/expenses_model.py`, `app/services/expenses/expenses_services.py`)
- Optional `participant_user_ids` on `POST /rooms/{room_id}/expenses` and `POST /rooms/{room_id}/expenses/for-member` — the expense is split evenly across just those members; omitted means all current room members
- `GET /rooms/{room_id}/expenses/{expense_id}` — expense detail with payer and per-participant `amount_paid`, `amount_owed`, `net`
- `settlements` on `GET /rooms/{room_id}/splits`: suggested "who pays whom" transfers, computed on read by greedy debt simplification over the active balances
- `Spendings.user_id` (FK to `Users.id`) and `Spendings.settled_at`, backfilled from the old `balance` table (migration `20260718165615`)
- Google `id_token` verification for Google OAuth login: tokens are now cryptographically verified via `google-auth`'s `verify_oauth2_token` (audience/issuer/signature checked against `GOOGLE_CLIENT_ID`) instead of the deprecated `tokeninfo` endpoint lookup (`app/utils/auth_providers.py`, `db/config.py`)
- `get_member_total_spent` model query for computing a member's total spend directly via `SUM(money)` instead of summing pending-expense rows in the service layer (`app/models/members/members_model.py`)
- Exiting a room and removing a member are now blocked while that member has a non-zero pending balance, whether they owe or are owed (`app/services/members/members_services.py`)
- Committed dbmate schema dump at `db/schema.sql`

### Changed

- Member balances (`GET /rooms/{room_id}/splits`, settle-all verification) are now read from the active `RoomBalanceSummary` rows — a signed net position (positive = owed to them, negative = they owe) — instead of being aggregated live on every read
- Settle-all now closes every active `RoomBalanceSummary` row for the room (`settled_at = now()`), opens a fresh zeroed row per current member, and stamps `settled` / `settled_at` on the room's unsettled `Spendings`
- `POST /rooms/{room_id}/expenses/for-member` takes `user_id` instead of `user_email`
- Room dashboard/summary response cleanup: removed `recent_expenses` from `GET /rooms/{room_id}` and dropped `email`, `role`, `total_spent` from per-member stats on `GET /rooms/{room_id}/dashboard`, leaving only `pending_amount` (`app/api/rooms/schemas.py`, `app/models/rooms/rooms_model.py`, `app/models/rooms/schemas.py`, `app/services/rooms/rooms_services.py`)
- Notifications routes moved under the room-scoped prefix and now require room membership instead of just authentication: `POST /notifications` → `POST /rooms/{room_id}/notifications`, with `room_id` taken from the path instead of the request body; all notification endpoints now depend on `require_room_member` instead of `get_current_user` (`app/api/notifications/api.py`, `app/api/notifications/schemas.py`) — fixes an IDOR where any authenticated user could post/list notifications or manage push subscriptions for a room they weren't a member of

### Fixed

- Member `total_spent` now reflects all of a member's spendings in the room (via `get_member_total_spent`), rather than only summing the subset of expenses currently marked pending (`app/services/members/members_services.py`)
- `RoomBalanceSummary` backfill missed legacy expenses with `settled IS NULL`, leaving their members at a zero balance (migration `20260724120000`)
- `SpendingSplits` / `RoomBalanceSummary` rebuilt from pending expenses with the payer always included as a participant, so an expense paid by someone who has since left the room is still credited (migration `20260724130000`)

### Removed

- `balance` table, and with it lump-sum (non-expense) settlement records
- "Contribute" feature: `POST /rooms/{room_id}/members/{user_id}/contribute`, with no replacement
- Single-member settle: `POST /rooms/{room_id}/splits/settle` and `POST /rooms/{room_id}/members/{user_id}/settle`
- Filtered settle-all (by date range and/or member subset) — `settle-all` now always settles the whole room

## [1.0.0] - 2026-07-16
### Added

- Filtered settle-all for splits: settle by date range and/or member subset, alongside the existing settle-all-unsettled flow (`app/api/splits/*`, `app/services/splits/splits_services.py`, `app/models/splits/splits_model.py`)
- Balance-based member pending calculation (paid vs. fair share vs. manual adjustments) replacing the raw per-user sum
- `app/utils/jwt_utils.py` extracted for JWT creation, shared by auth services
- Return invited by user name with invite/token GET request
- Added user profile picture, name, email to API endpoints
- Added expense settled at date with expense API endpoints
- Local dev and test database set up with Docker
- Pydantic row validators for model-layer raw SQL results (`app/models/<domain>/schemas.py`)
- Return type annotations on every router endpoint


### Changed

- Room creation simplified: `budget` field removed, `members`/`admin` are now derived from `UserRooms` instead of stored columns (`app/models/rooms/rooms_model.py`, `app/api/rooms/schemas.py`)
- `DELETE /rooms/{room_id}` authorization moved to the `require_room_admin` dependency instead of an in-service check
- Quoted all mixed-case table identifiers (`"Users"`, `"UserRooms"`, `"Spendings"`, `"Rooms"`, `"Invite"`) across models to fix Postgres case-folding issues
- Removed `Rooms.members` increment/decrement side-table bookkeeping now that member counts are derived
- Open auth for /invite/token GET request

### Fixed

- Replaced f-string-interpolated `WHERE` clauses in `get_filtered_unsettled_expenses` and `get_pending_for_user_filtered` with fully static, parameterized queries
- Fixed `syntax error at or near ":"` in `splits_model.py` filtered queries by switching `:param::type` casts to `CAST(:param AS type)`, since SQLAlchemy's `text()` treats `::` as an escaped literal colon rather than a Postgres typecast
- Removed leftover debug `print()` statements from splits settlement service

### Removed

- Notifications router disabled (kept in codebase, not wired up in `main.py`); expense edit/delete no longer emit notifications

## [0.0.1] - 2026-06-30
### Added

- Project scaffolding: FastAPI app and all workable route endpoints integration (#1)
- PostgreSQL(Supabase) integration with SQLAlchemy and dbmate migrations(#1)
