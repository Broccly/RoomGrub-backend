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

### Balance (Payment ledger)
Tracks settlement and contribution records.

| Field      | Type          | Notes                                                          |
|------------|---------------|----------------------------------------------------------------|
| id         | int PK        |                                                                |
| room       | int FK        | → Rooms.id                                                     |
| user       | text          | Email                                                          |
| amount     | decimal(10,2) | Positive = credit (contribution), negative = debit (settled)  |
| status     | enum          | `credit` or `debit`                                            |
| spending_id| int FK        | → Spendings.id — NULL for legacy lump-sum settlements          |
| created_at | timestamp     |                                                                |

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

### Pending Amount Calculation
```
pending = max(0, Σ unsettled_expenses + Σ legacy_debit_balance_records)
```
- `Spendings.settled = NULL or false` → counts as unsettled.
- `balance.spending_id IS NULL` → legacy lump-sum settlement (older records).
- `balance.spending_id IS NOT NULL` → per-expense settlement (new style).

### Settlement
When an admin settles a member:
1. For each unsettled `Spending`, insert a `balance` record with `amount = -money`, `status = debit`, `spending_id = expense.id`.
2. Mark all those `Spendings.settled = true`.
3. (Settle-all) Also delete any legacy lump-sum debit records for that scope.

### Room Deletion
- Blocked if **any** unsettled expenses remain.
- Cascade delete order: `balance` → `Spendings` → `Invite` → `push_subscriptions` → `notifications` → `UserRooms` → `Rooms`.

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
Users ──< Balance   >── Rooms
Users ──< Invite    >── Rooms          (invited_by)
Users ──< PushSubscription >── Rooms
Rooms ──< Notification
Spendings ──< Balance                  (spending_id, per-expense settlement)
```
