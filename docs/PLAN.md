# RoomGrub Backend — Migration Plan

## Goal

Extract all backend logic from the tightly-coupled Next.js app (`/Broccly/RoomGrub`) into a standalone **Python FastAPI** service. Both the RoomGrub web app and the Android app will then call this API.

---

## Phase 0 — Setup (Day 1)

- [ ] Initialize Python project with `pyproject.toml` / `requirements.txt`
- [ ] Set up FastAPI app factory in `app/main.py` with CORS and lifespan
- [ ] Set up async SQLAlchemy engine connecting to existing Supabase PostgreSQL
- [ ] Define all ORM models matching existing schema (no migrations needed)
- [ ] Set up Pydantic settings with `.env` support
- [ ] Write a `/health` endpoint to confirm DB connectivity
- [ ] Set up `pytest` with `pytest-asyncio` and a test DB session fixture

---

## Phase 1 — Auth & User Sync (Day 1–2)

- [ ] Implement `get_current_user` dependency (Supabase JWT verification)
- [ ] Implement `require_room_member` and `require_room_admin` dependencies
- [ ] Implement `POST /auth/sync-user` — upsert user from JWT claims
- [ ] Write tests for JWT verification (valid, expired, invalid, missing email)

---

## Phase 2 — Rooms (Day 2–3)

Extracted from:
- `src/app/actions.js` → `getUserRooms`
- `src/app/create_room/actions.js` → `createRoom`
- `src/app/[room_id]/actions.js` → `fetchHomeSummary`, `fetchRoomDashboard`
- `src/app/[room_id]/settings/actions.js` → `deleteRoom`

- [ ] `GET /rooms` — list user's rooms
- [ ] `POST /rooms` — create room + add creator as Admin in UserRooms
- [ ] `GET /rooms/{room_id}` — home summary (total purchases, pending amount, recent expenses)
- [ ] `GET /rooms/{room_id}/dashboard` — full member stats
- [ ] `DELETE /rooms/{room_id}` — delete room (Admin, all expenses settled guard)

---

## Phase 3 — Expenses (Day 3)

Extracted from:
- `src/app/[room_id]/addgroccery/actions.js` → `addExpense`, `addGroceryForFriend`
- `src/app/[room_id]/expenses/actions.js` → `fetchPaginatedExpenses`, `getRoomMembers`

- [ ] `GET /rooms/{room_id}/expenses` — paginated (cursor-based), with filters: settled, textSearch, user, dateFrom, dateTo
- [ ] `POST /rooms/{room_id}/expenses` — add expense for self
- [ ] `POST /rooms/{room_id}/expenses/for-member` — add for another member (Admin only)

---

## Phase 4 — Members (Day 4)

Extracted from:
- `src/app/[room_id]/members/actions.js` → `getMembers`, `updateMemberRole`, `removeMember`, `exitRoom`
- `src/app/[room_id]/members/[member_id]/actions.js` → `getMemberData`, `settleMember`, `recordContribution`

- [ ] `GET /rooms/{room_id}/members` — list with roles
- [ ] `GET /rooms/{room_id}/members/{member_id}` — detail: pending, total purchases, purchase history
- [ ] `PATCH /rooms/{room_id}/members/{member_id}/role` — change role (Admin)
- [ ] `DELETE /rooms/{room_id}/members/{member_id}` — remove (Admin, not self)
- [ ] `DELETE /rooms/{room_id}/members/me` — exit room (non-admin only)
- [ ] `POST /rooms/{room_id}/members/{member_id}/settle` — legacy settle
- [ ] `POST /rooms/{room_id}/members/{member_id}/contribute` — record contribution

---

## Phase 5 — Splits (Day 4–5)

Extracted from:
- `src/app/[room_id]/splits/actions.js` → `getSplitsData`, `settlePayment`, `settleAllPending`

- [ ] `GET /rooms/{room_id}/splits` — unsettled expenses + payments + members
- [ ] `POST /rooms/{room_id}/splits/settle` — settle one member (Admin)
- [ ] `POST /rooms/{room_id}/splits/settle-all` — settle all pending with server-side verification (Admin)

The settle-all endpoint must re-verify client-sent `pendingAmount` values server-side (0.01 tolerance) before writing.

---

## Phase 6 — Invites (Day 5)

Extracted from:
- `src/app/invite/[token]/actions.js` → `validateToken`, `createInvite`, `acceptInvite`, `rejectInvite`

- [ ] `POST /rooms/{room_id}/invites` — create invite (Admin)
- [ ] `GET /invites/{token}` — validate (returns room info, invitedBy, daysLeft)
- [ ] `POST /invites/{token}/accept` — join room (idempotent)
- [ ] `POST /invites/{token}/reject` — reject invite

---

## Phase 7 — Notifications & Push (Day 5–6)

Extracted from:
- `src/app/api/notifications/route.js`
- `src/services/NotificationService.js`

- [ ] `POST /notifications` — create DB notification record + send web push via `pywebpush`
- [ ] `GET /rooms/{room_id}/notifications` — list activity notifications
- [ ] `POST /rooms/{room_id}/push-subscriptions` — register/update push subscription
- [ ] `DELETE /rooms/{room_id}/push-subscriptions` — unregister

VAPID keys from env: `VAPID_SUBJECT`, `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` (same keys as the Next.js app).

---

## Phase 8 — Testing & Hardening (Day 6–7)

- [ ] Write integration tests for all endpoints against a real test DB
- [ ] Ensure all admin-only routes return 403 for Member role
- [ ] Ensure unauthenticated requests return 401
- [ ] Test settle-all amount mismatch detection
- [ ] Test invite expiry (7 days)
- [ ] Test room delete blocked when unsettled expenses exist

---

## Phase 9 — Web App Migration (Day 7–8)

Update `RoomGrub` Next.js app to call this API instead of using Server Actions:
- [ ] Replace all `'use server'` action files with `fetch()` calls to the FastAPI API
- [ ] Pass Supabase access token from client session to API requests
- [ ] Remove `src/database/` ORM models (no longer used in frontend)
- [ ] Remove `src/services/NotificationService.js` (notifications now sent server-side in FastAPI)
- [ ] Keep Supabase Auth client for login/logout only

---

## Phase 10 — Android App Integration (Day 8–9)

- [ ] Document API base URL config in the Android app (`RoomGrub-native`)
- [ ] Confirm Supabase auth token is forwarded correctly in all API calls
- [ ] Test all endpoints from the Android app
- [ ] Handle token refresh before expiry (1 hour Supabase default)

---

## Deployment

- FastAPI app runs as a standalone service (Docker / Railway / Render / Fly.io)
- Environment variables from `.env` / secrets manager
- Supabase DB stays as-is (no schema changes in Phase 0–9)
- CORS configured for web and mobile origins
