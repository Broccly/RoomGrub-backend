# RoomGrub — Domain Model

## What is RoomGrub?

RoomGrub is a shared-expense tracker for people living together (roommates). Members of a **Room** log grocery and expense purchases. An admin can view each member's total spend, settle their balance, and track who owes what in real time. Both a web app and an Android app consume the same backend.

---

## Core Entities

### User
Represents a registered person (authenticated via Supabase Auth / Google OAuth).

| Field     | Type   | Notes                          |
|-----------|--------|--------------------------------|
| id        | int PK | Internal DB id                 |
| uid       | uuid   | Supabase Auth UID              |
| email     | text   | Unique, used as FK throughout  |
| name      | text   |                                |
| profile   | text   | Avatar URL                     |

### Room
A shared household / group.

| Field   | Type  | Notes                          |
|---------|-------|--------------------------------|
| id      | int PK|                                |
| members | int   | Denormalized count             |
| budget  | float | Optional monthly budget        |
| admin   | text  | Email of the creator/admin     |
| uid     | uuid  | Optional external reference    |

### UserRoom (membership)
Many-to-many join between User ↔ Room with a role.

| Field     | Type      | Notes                   |
|-----------|-----------|-------------------------|
| id        | int PK    |                         |
| user_id   | int FK    | → Users.id              |
| room_id   | int FK    | → Rooms.id              |
| role      | text      | `Admin` or `Member`     |
| joined_at | timestamp |                         |

### Spendings (Expenses)
A purchase entry made by a member.

| Field      | Type           | Notes                                      |
|------------|----------------|--------------------------------------------|
| id         | int PK         |                                            |
| room       | int FK         | → Rooms.id                                 |
| user       | text           | Email of the spender                       |
| material   | text           | Item / description                         |
| money      | decimal(10,2)  | Amount spent                               |
| created_at | timestamp      | Defaults to NOW                            |
| settled    | bool           | NULL / false = pending, true = settled     |

### Balance (Payment ledger) — **deprecated, being removed (see SpendingSplits / RoomBalanceSummary below)**
Tracks settlement and contribution records. Being replaced entirely by `RoomBalanceSummary`'s historical ledger; dropped once `expenses`/`rooms` models stop reading it for `settled_at` display (tracked in docs/TODOS.md Phase 5). The "contribute" feature that wrote credit rows here is being removed outright, no replacement.

| Field      | Type          | Notes                                                          |
|------------|---------------|------------------------------------------------------------------|
| id         | int PK        |                                                                |
| room       | int FK        | → Rooms.id                                                     |
| user       | text          | Email                                                          |
| amount     | decimal(10,2) | Positive = credit (contribution), negative = debit (settled)  |
| status     | enum          | `credit` or `debit`                                            |
| spending_id| int FK        | → Spendings.id — NULL for legacy lump-sum settlements          |
| created_at | timestamp     |                                                                |

### SpendingSplits *(new domain, rolling out — see docs/domain-overview.html)*
Precomputed per-participant share of one expense. A row's existence **is** the participation record — no separate participants table. `net` (a member's balance contribution from this expense) is **not stored**; compute it as `amount_paid - amount_owed` wherever needed.

| Field       | Type          | Notes                                                 |
|-------------|---------------|----------------------------------------------------------|
| id          | int PK        |                                                         |
| spending_id | int FK        | → Spendings.id                                         |
| user_id     | int FK        | → Users.id                                             |
| amount_paid | decimal(10,2) | Non-zero only on the payer's row (= Spendings.money)   |
| amount_owed | decimal(10,2) | Even split: Spendings.money / participant_count        |
| created_at  | timestamp     |                                                         |

Unique on `(spending_id, user_id)`. When an expense is created with an explicit `participant_user_ids` list, only those members get a row. Legacy expenses (created before this feature, or by clients that haven't updated) are backfilled/defaulted to "all current room members" — indistinguishable in shape from an explicit selection, no provenance flag.

### RoomBalanceSummary *(new domain, rolling out — replaces Balance entirely)*
A **historical ledger**, not just a snapshot: it holds one **active** row per `(room, user)` plus any number of **closed/historical** rows from past full settlements. This is the read-fast source of truth that `GET /splits` reads from (Redis caches on top, doesn't replace it).

| Field          | Type          | Notes                                                              |
|----------------|---------------|------------------------------------------------------------------------|
| id             | int PK        |                                                                       |
| room_id        | int FK        | → Rooms.id                                                           |
| user_id        | int FK        | → Users.id                                                           |
| pending_amount | decimal(10,2) | Signed net: positive = owed to them, negative = they owe              |
| settled_at     | timestamp     | NULL = active row; set = historical, closed-out settlement record     |
| updated_at     | timestamp     | Refreshed whenever the active row's pending_amount changes            |

Constraint: at most one row per `(room_id, user_id)` may have `settled_at IS NULL` (partial unique index) — that's the *active* row. All others are permanent history.

- **Expense add/edit/remove and partial/filtered settles** update the active row's `pending_amount` in place.
- **A full settle** (single member or whole room) closes the active row (stamps `settled_at = now()`, freezing it as a record of "this much was owed, settled at this time") and opens a brand-new active row at `pending_amount = 0` for that member going forward. This is how users can look back and see when they settled with the room and for how much — the closed rows *are* the settlement history, no separate transfer log needed.
- "Who pays whom" (pairwise transfers) is **not persisted** — it's computed on read from the small set of active rows via a greedy debt-simplification pass (sort debtors/creditors, match largest-to-largest), the same technique Splitwise uses. This avoids O(n²) pairwise-row maintenance on every write in a write-heavy system.

### Invite
One-time invite link to join a room.

| Field      | Type      | Notes                                         |
|------------|-----------|-----------------------------------------------|
| id         | int PK    |                                               |
| room       | int FK    | → Rooms.id                                    |
| invited_by | int FK    | → Users.id                                    |
| token      | uuid      | Unique, used in share URL                     |
| status     | text      | `pending` / `accepted` / `rejected` / `expired` |
| created_at | timestamp |                                               |
| updated_at | timestamp |                                               |

Invite expires after **7 days**.

### Notification
Activity log for in-app and push notifications.

| Field         | Type      | Notes                                                              |
|---------------|-----------|--------------------------------------------------------------------|
| id            | int PK    |                                                                    |
| room_id       | int FK    | → Rooms.id                                                         |
| triggered_by  | int FK    | → Users.id                                                         |
| activity_type | enum      | `payment` / `grocery` / `expense` / `member_join` / `member_leave` |
| title         | string    |                                                                    |
| message       | text      |                                                                    |
| data          | jsonb     | Extra metadata                                                     |
| created_at    | timestamp |                                                                    |

### PushSubscription
Web Push subscription for a user in a room.

| Field      | Type      | Notes                                 |
|------------|-----------|---------------------------------------|
| id         | int PK    |                                       |
| user_id    | int FK    | → Users.id                            |
| room_id    | int FK    | → Rooms.id                            |
| endpoint   | text      | Push endpoint URL                     |
| p256dh_key | text      | Encryption key                        |
| auth_key   | text      | Auth secret                           |
| created_at | timestamp |                                       |
| updated_at | timestamp |                                       |

Unique constraint on `(user_id, room_id)`.

---

## Business Rules

### Roles
- Every room has at least one `Admin`.
- Admins cannot demote themselves or leave the room.
- Only Admins can: add expenses for others, change member roles, remove members, create invite links, settle payments, delete the room.

### Pending Amount Calculation — **current (production) behavior, being replaced**
```
pending = max(0, Σ unsettled_expenses + Σ legacy_debit_balance_records)
```
- `Spendings.settled = NULL or false` → counts as unsettled.
- `balance.spending_id IS NULL` → legacy lump-sum settlement (older records).
- `balance.spending_id IS NOT NULL` → per-expense settlement (new style).
- Computed **live**, every read, dividing each expense evenly across **all current `UserRooms` members** — not the explicit participant set (there isn't one today).

### Pending Amount Calculation — **new domain (rolling out, see SpendingSplits / RoomBalanceSummary above)**
```
pending_amount = active RoomBalanceSummary row for (room, user)
```
Precomputed at write time (expense add/edit/remove), not recomputed on read — the read path is a single indexed lookup (cache-aside via Redis), not a live aggregation. Each expense splits only across its explicit `SpendingSplits` participants (or, for legacy expenses, all room members at creation time — see SpendingSplits above).

### Settlement — **current (production) behavior, being replaced**
When an admin settles a member:
1. For each unsettled `Spending`, insert a `balance` record with `amount = -money`, `status = debit`, `spending_id = expense.id`.
2. Mark all those `Spendings.settled = true`.
3. (Settle-all) Also delete any legacy lump-sum debit records for that scope.

### Settlement — **new domain (rolling out)**
- **Full settle** (single member or settle-all): close the member's active `RoomBalanceSummary` row (`settled_at = now()`), open a fresh active row at `pending_amount = 0`. The closed row is the permanent settlement-history record.
- **Partial/filtered settle**: update the active row's `pending_amount` in place — not a close-out event, since the member's balance isn't fully zeroed.
- In both cases, mark the relevant `Spendings.settled = true` and set `Spendings.settled_at = now()` (replacing the `balance` join used for that timestamp today).
- The "contribute" feature (lump-sum credit into `balance` without an expense) is **removed entirely**, no replacement.

### Room Deletion
- Blocked if **any** unsettled expenses remain.
- Cascade delete order (current): `balance` → `Spendings` → `Invite` → `push_subscriptions` → `notifications` → `UserRooms` → `Rooms`.
- New domain adds `RoomBalanceSummary` (explicit delete, all rows for the room including history) to the order; `SpendingSplits` cascades automatically via its FK to `Spendings`. Once `balance` is dropped (Phase 5), it drops out of this order entirely.

### Invite Flow
1. Admin calls `POST /rooms/{room_id}/invites` → returns a UUID token.
2. Share URL: `{APP_URL}/invite/{token}`.
3. Recipient: `GET /invites/{token}` to validate, `POST /invites/{token}/accept` to join.
4. Token expires after 7 days (checked at validate and accept time).

---

## Relationships Diagram (simplified)

```
Users ──< UserRooms >── Rooms
Users ──< Spendings >── Rooms
Users ──< Balance   >── Rooms          (deprecated, being removed)
Users ──< Invite    >── Rooms          (invited_by)
Users ──< PushSubscription >── Rooms
Rooms ──< Notification
Spendings ──< Balance                  (deprecated — spending_id, per-expense settlement)

-- new domain (rolling out) --
Spendings ──< SpendingSplits >── Users       (participants + precomputed share, per expense)
Users ──< RoomBalanceSummary >── Rooms       (one active row + N historical rows per member per room)
```
