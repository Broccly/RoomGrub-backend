# RoomGrub Backend — TODO Checklist

## Project Setup
- [x] Create `pyproject.toml` with project metadata
- [x] Create `requirements.txt` with pinned dependencies
- [x] Create `.env.example` with all required env vars documented
- [x] Create `db/config.py` — per-variable env getter functions
- [x] Create `db/engine.py` — sync SQLAlchemy engine + `db_conn()` session generator
- [x] Scaffold `app/api/`, `app/models/`, `app/services/`, `app/dependencies/` folder structure
- [ ] Fix `main.py` — router registration is currently broken (imports routers as functions, not router objects)
- [ ] `GET /api/v1/health` — simple endpoint to confirm DB connectivity
- [ ] Set up `pytest` with a test DB session fixture and test client in `tests/conftest.py`

## Pydantic Schemas
Each domain's schemas live in `app/api/<domain>/schemas.py`:
- [ ] `app/api/auth/schemas.py` — UserSyncRequest, UserResponse
- [ ] `app/api/rooms/schemas.py` — RoomCreate, RoomResponse, RoomSummary, MemberStat, DashboardResponse
- [ ] `app/api/expenses/schemas.py` — ExpenseCreate, ExpenseForMemberCreate, ExpenseResponse, PaginatedExpensesResponse
- [ ] `app/api/members/schemas.py` — MemberResponse, MemberDetail, RoleUpdate
- [ ] `app/api/splits/schemas.py` — SplitsData, SettleRequest, SettleAllRequest, MemberBalance
- [ ] `app/api/invites/schemas.py` — InviteCreate, InviteValidation, InviteResponse
- [ ] `app/api/notifications/schemas.py` — NotificationCreate, PushSubscriptionUpsert

## Dependencies
- [ ] `app/dependencies/current_user.py` — `get_current_user` (JWT verify + DB lookup)
- [ ] `app/dependencies/room_access.py` — `require_room_member`, `require_room_admin`

## Routers & Services

### Auth
- [ ] `POST /api/v1/auth/sync-user` — upsert user from JWT claims
  - Router: `app/api/auth/api.py`
  - Service: `app/services/auth/auth_services.py`
  - Model: `app/models/auth/auth_model.py`

### Rooms
- [ ] `GET /api/v1/rooms` — list rooms for current user
- [ ] `POST /api/v1/rooms` — create room (atomic: create Room + add creator as Admin in UserRooms)
- [ ] `GET /api/v1/rooms/{room_id}` — home summary (total purchases, pending, recent 5 expenses)
- [ ] `GET /api/v1/rooms/{room_id}/dashboard` — member stats (purchases, pending per member)
- [ ] `DELETE /api/v1/rooms/{room_id}` — delete room (Admin, 0 unsettled guard, cascade delete)
  - Router: `app/api/rooms/api.py`
  - Service: `app/services/rooms/rooms_services.py`
  - Model: `app/models/rooms/rooms_model.py`

### Expenses
- [ ] `GET /api/v1/rooms/{room_id}/expenses` — paginated, cursor-based, with filters (settled, text, user, dateFrom, dateTo)
- [ ] `POST /api/v1/rooms/{room_id}/expenses` — add expense for self
- [ ] `POST /api/v1/rooms/{room_id}/expenses/for-member` — add for another member (Admin)
  - Router: `app/api/expenses/api.py`
  - Service: `app/services/expenses/expenses_services.py`
  - Model: `app/models/expenses/expenses_model.py`

### Members
- [ ] `GET /api/v1/rooms/{room_id}/members` — list with roles
- [ ] `GET /api/v1/rooms/{room_id}/members/{member_id}` — detail + pending + purchase history
- [ ] `PATCH /api/v1/rooms/{room_id}/members/{member_id}/role` — update role (Admin, can't demote self)
- [ ] `DELETE /api/v1/rooms/{room_id}/members/{member_id}` — remove (Admin, not self)
- [ ] `DELETE /api/v1/rooms/{room_id}/members/me` — exit room (non-admin only)
- [ ] `POST /api/v1/rooms/{room_id}/members/{member_id}/settle` — legacy lump-sum settle
- [ ] `POST /api/v1/rooms/{room_id}/members/{member_id}/contribute` — record contribution
  - Router: `app/api/members/api.py`
  - Service: `app/services/members/members_services.py`
  - Model: `app/models/members/members_model.py`

### Splits
- [ ] `GET /api/v1/rooms/{room_id}/splits` — unsettled expenses + lump-sum debits + members
- [ ] `POST /api/v1/rooms/{room_id}/splits/settle` — settle one member (Admin)
- [ ] `POST /api/v1/rooms/{room_id}/splits/settle-all` — settle all with server-side amount verification (Admin)
  - Router: `app/api/splits/api.py`
  - Service: `app/services/splits/splits_services.py`
  - Model: `app/models/splits/splits_model.py`

### Invites
- [ ] `POST /api/v1/rooms/{room_id}/invites` — create invite link (Admin, generates UUID token)
- [ ] `GET /api/v1/invites/{token}` — validate token (returns room info, daysLeft, invitedBy)
- [ ] `POST /api/v1/invites/{token}/accept` — join room (idempotent, increments Room.members)
- [ ] `POST /api/v1/invites/{token}/reject` — mark invite rejected
  - Router: `app/api/invites/api.py`
  - Service: `app/services/invites/invites_services.py`
  - Model: `app/models/invites/invites_model.py`

### Notifications
- [ ] `POST /api/v1/notifications` — create DB record + send push to all room subscribers
- [ ] `GET /api/v1/rooms/{room_id}/notifications` — list room activity notifications
- [ ] `POST /api/v1/rooms/{room_id}/push-subscriptions` — upsert subscription (endpoint, p256dh, auth)
- [ ] `DELETE /api/v1/rooms/{room_id}/push-subscriptions` — remove subscription
  - Router: `app/api/notifications/api.py`
  - Service: `app/services/notifications/notifications_services.py`
  - Model: `app/models/notifications/notifications_model.py`

## Utilities
- [ ] `app/utils/push.py` — pywebpush send helper, handle 410 (stale subscription removal)
- [ ] `app/utils/pagination.py` — cursor encode/decode helpers

## Business Logic Checks (must implement in services)
- [ ] Settle-all: server-side re-verification of pending amount per member (0.01 tolerance)
- [ ] Room delete: block if any `Spendings.settled IS NOT TRUE` in the room
- [ ] Invite accept: idempotent (already a member → return success without duplicate insert)
- [ ] Role update: prevent self-demotion from Admin
- [ ] Remove member: prevent self-removal by Admin (use `/members/me` to exit)
- [ ] Exit room: only non-Admin can exit

## Tests
- [ ] `tests/test_auth.py` — sync-user, JWT expired, JWT invalid
- [ ] `tests/test_rooms.py` — create, list, summary, dashboard, delete (with settled/unsettled guard)
- [ ] `tests/test_expenses.py` — add, paginated list, filters, for-member (admin guard)
- [ ] `tests/test_members.py` — list, detail, role update, remove, exit
- [ ] `tests/test_splits.py` — get splits, settle, settle-all (amount mismatch detection)
- [ ] `tests/test_invites.py` — create, validate, accept (idempotent), reject, expired

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
