# RoomGrub Backend — TODO Checklist

## Project Setup
- [ ] Create `pyproject.toml` with project metadata
- [ ] Create `requirements.txt` with pinned dependencies
- [ ] Create `.env.example` with all required env vars documented
- [ ] Create `app/main.py` — FastAPI app factory (CORS, lifespan, router registration)
- [ ] Create `app/config.py` — pydantic-settings based config
- [ ] Create `app/database.py` — async SQLAlchemy engine, session factory, `get_db` dependency
- [ ] Create `tests/conftest.py` — test DB fixture, override `get_db`, test client

## ORM Models
- [ ] `app/models/user.py` — User
- [ ] `app/models/room.py` — Room
- [ ] `app/models/user_room.py` — UserRoom
- [ ] `app/models/spendings.py` — Spendings (expense)
- [ ] `app/models/balance.py` — Balance (settlement ledger)
- [ ] `app/models/invite.py` — Invite
- [ ] `app/models/notification.py` — Notification
- [ ] `app/models/push_subscription.py` — PushSubscription

## Pydantic Schemas
- [ ] `app/schemas/auth.py` — UserSyncRequest, UserResponse
- [ ] `app/schemas/room.py` — RoomResponse, RoomSummary, MemberStat, DashboardResponse
- [ ] `app/schemas/expense.py` — ExpenseCreate, ExpenseForMemberCreate, ExpenseResponse, PaginatedExpensesResponse
- [ ] `app/schemas/member.py` — MemberResponse, MemberDetail, RoleUpdate
- [ ] `app/schemas/split.py` — SplitsData, SettleRequest, SettleAllRequest, MemberBalance
- [ ] `app/schemas/invite.py` — InviteCreate, InviteValidation, InviteResponse
- [ ] `app/schemas/notification.py` — NotificationCreate, PushSubscriptionUpsert

## Dependencies
- [ ] `app/dependencies/auth.py` — `get_current_user` (JWT verify + DB lookup)
- [ ] `app/dependencies/room_access.py` — `require_room_member`, `require_room_admin`

## Routers & Services

### Auth
- [ ] `POST /auth/sync-user` — upsert user from JWT claims

### Rooms
- [ ] `GET /rooms` — list rooms for current user
- [ ] `POST /rooms` — create room (atomic: create Room + add Admin UserRoom)
- [ ] `GET /rooms/{room_id}` — home summary (total purchases, pending, recent 5 expenses)
- [ ] `GET /rooms/{room_id}/dashboard` — member stats (purchases, pending per member)
- [ ] `DELETE /rooms/{room_id}` — delete room (Admin, 0 unsettled guard, cascade delete)

### Expenses
- [ ] `GET /rooms/{room_id}/expenses` — paginated, cursor-based, with filters
- [ ] `POST /rooms/{room_id}/expenses` — add expense for self
- [ ] `POST /rooms/{room_id}/expenses/for-member` — add for another member (Admin)

### Members
- [ ] `GET /rooms/{room_id}/members` — list with roles
- [ ] `GET /rooms/{room_id}/members/{member_id}` — detail + pending + purchase history
- [ ] `PATCH /rooms/{room_id}/members/{member_id}/role` — update role (Admin, can't demote self)
- [ ] `DELETE /rooms/{room_id}/members/{member_id}` — remove (Admin, not self)
- [ ] `DELETE /rooms/{room_id}/members/me` — exit room (non-admin only)
- [ ] `POST /rooms/{room_id}/members/{member_id}/settle` — legacy lump-sum settle
- [ ] `POST /rooms/{room_id}/members/{member_id}/contribute` — record contribution

### Splits
- [ ] `GET /rooms/{room_id}/splits` — unsettled expenses + lump-sum debits + members
- [ ] `POST /rooms/{room_id}/splits/settle` — settle one member (Admin)
- [ ] `POST /rooms/{room_id}/splits/settle-all` — settle all with server-side amount verification (Admin)

### Invites
- [ ] `POST /rooms/{room_id}/invites` — create invite link (Admin, generates UUID token)
- [ ] `GET /invites/{token}` — validate token (returns room info, daysLeft, invitedBy)
- [ ] `POST /invites/{token}/accept` — join room (idempotent, increments Room.members)
- [ ] `POST /invites/{token}/reject` — mark invite rejected

### Notifications
- [ ] `POST /notifications` — create DB record + send push to all room subscribers
- [ ] `GET /rooms/{room_id}/notifications` — list room activity notifications
- [ ] `POST /rooms/{room_id}/push-subscriptions` — upsert subscription (endpoint, p256dh, auth)
- [ ] `DELETE /rooms/{room_id}/push-subscriptions` — remove subscription

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
- [x] `DOMAIN.md` — entities, business rules, relationships
- [x] `ARCHITECTURE.md` — system design, project structure, API surface
- [x] `AUTH.md` — JWT verification, user sync, role guards
- [x] `PLAN.md` — phased migration plan
- [x] `TODOS.md` — this file
- [x] `SETUP.md` — local dev setup guide
- [ ] `README.md` — top-level overview (after implementation)
