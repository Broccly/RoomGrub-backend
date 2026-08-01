# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [Unreleased]
### Added

- Redis (Upstash) cache-aside layer for auth (`get_current_user`) and room-membership checks (`require_room_member`), with active invalidation on room create/delete, invite accept, role change, and member remove/exit (`app/cache/auth_cache.py`, `db/redis_client.py`, dependency/service wiring)
- Fail-open Redis handling: cache read/write/invalidate errors are caught and logged as warnings, falling back to Postgres instead of failing the request
- In-process circuit breaker (`db/redis_circuit.py`) that skips Redis entirely for 30s after a failure, so a Redis outage doesn't add per-request timeout latency
- Google `id_token` verification for Google OAuth login: tokens are now cryptographically verified via `google-auth`'s `verify_oauth2_token` (audience/issuer/signature checked against `GOOGLE_CLIENT_ID`) instead of the deprecated `tokeninfo` endpoint lookup (`app/utils/auth_providers.py`, `db/config.py`)
- `get_member_total_spent` model query for computing a member's total spend directly via `SUM(money)` instead of summing pending-expense rows in the service layer (`app/models/members/members_model.py`)
- Restrict exit room and remove member from room, if user have pending amount(owed, owed)

### Changed

- Room dashboard/summary response cleanup: removed `recent_expenses` from `GET /rooms/{room_id}/summary` and dropped `email`, `role`, `total_spent` from per-member stats, leaving only `pending_amount` (`app/api/rooms/schemas.py`, `app/models/rooms/rooms_model.py`, `app/models/rooms/schemas.py`, `app/services/rooms/rooms_services.py`)
- Notifications routes moved under the room-scoped prefix and now require room membership instead of just authentication: `POST /notifications` → `POST /rooms/{room_id}/notifications`, with `room_id` taken from the path instead of the request body; all notification endpoints now depend on `require_room_member` instead of `get_current_user` (`app/api/notifications/api.py`, `app/api/notifications/schemas.py`) — fixes an IDOR where any authenticated user could post/list notifications or manage push subscriptions for a room they weren't a member of

### Fixed

- Member `total_spent` now reflects all of a member's spendings in the room (via `get_member_total_spent`), rather than only summing the subset of expenses currently marked pending (`app/services/members/members_services.py`)

## [1.0.0] - 2026-07-04
### Added

- Filtered settle-all for splits: settle by date range and/or member subset, alongside the existing settle-all-unsettled flow (`app/api/splits/*`, `app/services/splits/splits_services.py`, `app/models/splits/splits_model.py`)
- Balance-based member pending calculation (paid vs. fair share vs. manual adjustments) replacing the raw per-user sum
- `app/utils/jwt_utils.py` extracted for JWT creation, shared by auth services
- Return invited by user name with invite/token GET request
- Added user profile picture, name, email to API endpoints
- Added expense settled at date with expense API endpoints
- Local dev and test database set up with Docker


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
- 