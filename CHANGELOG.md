# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


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