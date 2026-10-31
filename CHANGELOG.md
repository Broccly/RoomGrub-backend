# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [Unreleased]
### Added

- Groundwork for guest access ([docs/GUEST_ACCESS.md](docs/GUEST_ACCESS.md), Phase A), migration `20261030120000_users_type_and_room_cleanup`: `Users.type` (`registered` / `guest` / `placeholder`; only `registered` is created so far), and `Rooms.name` on databases that lacked it
- `POST /rooms/{room_id}/splits/settle-all` accepts `user_id` per member; `user_email` is still accepted, and one of the two is required (`422`)
- `GET /rooms/{room_id}/expenses` takes a `user_id` (payer) filter
- Room responses (`GET` / `POST /rooms`, `GET /rooms/{room_id}`, dashboard) include `admin_user_id` and `admin_name`. The three admin fields now always describe the room's longest-standing Admin; before, `admin` was an arbitrary Admin
- Room names (guest access Phase B): `POST /rooms` takes an optional `{name}` (1–50 characters after trimming, else `422`; no body still works), every room response includes `name` (`null` for older rooms), and `PATCH /rooms/{room_id}` lets an Admin rename the room
- Invite responses (`POST /rooms/{room_id}/invites`, `GET /invites/{token}`) include `room_name`
- `GET /users/me` (own `id`, `email`, `name`, `profile`, `type`) and `PATCH /users/me` to edit your own `name` and avatar. The avatar is a link stored in `profile`: an `https` URL on a host in the new optional `AVATAR_ALLOWED_HOSTS` setting (default: the Google and Facebook photo hosts); `null` removes it

### Changed

- The payer is looked up by `Spendings.user_id` everywhere (expense list and detail, member detail, dashboard, `GET /splits`) instead of by the legacy `Spendings."user"` email, which is now nullable and no longer read
- `Users.email` is nullable (`''` became `NULL`), so every email field in responses (`email`, `user`, `user_email`, `from_user_email`, `to_user_email`, `invited_by_email`, `admin`) may be `null`. No user without an email can be created yet
- The access token omits the `email` claim when the user has no email
- `Users.uid` and `Rooms.uid` are stable UUIDs generated on insert; existing values were regenerated, and login no longer rewrites `Users.uid` as `"<provider>:<email>"`. Neither is exposed by the API
- Several users can share the same avatar (`Users_profile_key` dropped)
- Login no longer overwrites a user's name and avatar with the provider's on every sign-in: the provider's values only fill ones that are empty, so edits made with `PATCH /users/me` stick. Login also clears the cached user (`auth:user:{id}`), which was never invalidated before, so a changed name or photo could stay stale for up to 7 days

- Exiting a room (`DELETE /rooms/{room_id}/members/me`) and removing a member (`DELETE /rooms/{room_id}/members/{user_id}`) are now blocked (`400`) while the member is part of any unsettled expense, even when their net balance is zero. This replaces the net-balance check, which it covers: a balance only moves through unsettled expenses. Unsettled expenses can still be edited or deleted, which would otherwise change a departed member's balance or drop a departed payer's credit. Settle the room first (`members_model.has_unsettled_splits`)
- `members_services.exit_room` and `remove_member` raise plain exceptions; the router converts them, with status codes and messages unchanged
- `POST /rooms/{room_id}/expenses` and `/expenses/for-member` reject (`400`) a `participant_user_ids` list that leaves out the payer. Such an expense recorded no payment, so its balances didn't add up
- Editing or deleting an expense whose payer has left the room returns `400`
- A money-only edit keeps the expense's existing split exactly, and returns `400` if that split doesn't include the payer (older expenses created without them)
- `PATCH /rooms/{room_id}/expenses/{expense_id}` rejects (`422`) any field besides `material`, `money`, `created_at` and `participant_user_ids`. Sending a payer such as `user_id` used to be silently ignored; the payer can't be changed
- `expenses_services.add_expense` and `add_expense_for_member` raise plain exceptions; the router converts them, with status codes and messages unchanged

### Removed

- Legacy columns that existed only in the Supabase database: `Rooms.members`, `Rooms.budget`, `Rooms.admin` (with `Rooms_admin_fkey`) and `Users.role`, and the `admin_can_delete` / `admin_can_update` RLS policies on `Spendings` that read `Users.role`. The backend never used them; room roles are `UserRooms.role`

### Fixed

- A money-only expense edit dropped split members who had left the room, and the payer's credit with them, so the room's balances no longer summed to zero
- Editing participants of an expense whose payer had left skipped the "payer must be in the split" check and lost the payer's credit

## [1.3.0] - 2026-10-21
### Added

- Refresh tokens, so a signed-in device is no longer signed out when its access token expires. `POST /auth/login` now also returns `refresh_token` and `expires_in`; each login starts its own session ("family"), one per device (`app/services/auth/auth_services.py`)
- `POST /api/v1/auth/refresh` — trades a refresh token for a new access + refresh token pair. Tokens are single-use and rotate on every call, each new one with a fresh `REFRESH_TOKEN_EXPIRY_DAYS` lifetime (sliding idle window). Replaying a spent token more than 30 seconds after it was used revokes that device's whole session; unknown, expired, revoked and replayed tokens all answer `401 Invalid refresh token`
- `POST /api/v1/auth/logout` — revokes the session the given refresh token belongs to; always 204
- `refresh_tokens` table (migration `20261005120000`): one row per issued token, storing only its SHA-256 hash, with `ON DELETE CASCADE` from `Users`. A user's expired and revoked rows are deleted at their next login
- Refresh and logout serialise per session with a Postgres advisory lock on the token's family (`auth_model.lock_refresh_token_family`), so a family revocation cannot miss a token issued by a concurrent refresh of another token in the same family
- `REFRESH_TOKEN_EXPIRY_DAYS` env var (default 90)
- e2e coverage for rotation, the grace window, reuse detection, expiry, logout and cleanup (`tests/e2e/test_auth.py`)
- `PATCH /rooms/{room_id}/expenses/{expense_id}` accepts `participant_user_ids` to change who an expense is split between. The list must be non-empty, all room members, and include the payer (`400` otherwise); balances are re-split in the same transaction
- `GET /rooms/{room_id}/splits` returns what the app's Home screen needs in one call: per member `user_id`, `role`, `unsettled_spent`, `unsettled_share`, `total_spent`; per settlement `from_user_id` / `to_user_id`; and room `unsettled_count`, `total_spent`, `last_settled_at`. `?include_expenses=false` skips the `unsettled_expenses` list. All amounts are rounded to 2 decimals
- `GET /rooms` returns `member_preview` per room — the first 4 members by join date as `{profile, label}` — so the rooms list can draw its avatars without calling `/members` once per room. Fetched for all rooms in one query (`rooms_model.get_member_previews`)
- `GET /rooms/{room_id}/expenses/frequent-items?limit=6` returns `{items}`, the room's most-used item names, for the app's suggestion chips. It ranks the latest 100 expenses the same way the app did on the phone: comma-separated names, case-insensitive, most used first, ties to the most recent, shown with the latest spelling

### Changed

- `GET /splits` lists every current room member, with zeros when they have no balance yet (a new room used to return no members), plus anyone who left with a non-zero balance (`role: null`). `total_pending` is typed as a float instead of an int
- Room-scoped routes return `404 Room not found` for a room that doesn't exist (e.g. deleted) instead of `403`, so clients can tell it apart from a room they aren't a member of, which stays `403 Not a member of this room`. The extra lookup runs only when access is denied (`require_room_member`)
- `PATCH` and `DELETE /rooms/{room_id}/expenses/{expense_id}` are no longer Admin-only: the expense's owner (its payer, `Spendings.user_id`) can also edit — participants included — and delete it while it is unsettled. Other members get `403`
- `PATCH` and `DELETE /rooms/{room_id}/expenses/{expense_id}` return `409 Settled expenses can't be changed` for a settled expense. Previously they reversed its splits against the members' current balances (`expenses_services.edit_expense`, `remove_expense`)
- **Access tokens now live 15 minutes instead of 24 hours.** `JWT_ACCESS_EXPIRY_MINUTES` (default 15) replaces `JWT_EXPIRY_HOURS`, which is no longer read. Clients must call `/auth/refresh` on `401 Token expired`; a client that does not will be signed out every 15 minutes
- The database URL is now built with SQLAlchemy's `URL.create` instead of an f-string, so a `DB_PASSWORD` (or user) containing `@`, `:`, `/`, `#`, `?` or `%` no longer breaks every DB connection (`db/engine.py`)
- Docs rewritten around the two-token flow: `AUTH.md`, `ARCHITECTURE.md`, `DOMAIN.md`, `SETUP.md`, `MIGRATIONS.md`, `AGENTS.md`, `README.md`, `tests/README.md`, `PLAN.md`, `TODOS.md`
- `db/schema.sql` re-dumped: it now includes `fcm_tokens` and `refresh_tokens` and no longer has `push_subscriptions`

### Fixed

- Editing `money` on an expense whose payer was not in the split dropped all its splits. The payer is now read from `Spendings.user_id`, so the splits are re-applied

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
