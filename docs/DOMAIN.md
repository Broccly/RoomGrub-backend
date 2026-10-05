# RoomGrub — Domain Model

## What is RoomGrub?

RoomGrub is a shared-expense tracker for people living together (roommates). Members of a **Room** log grocery and expense purchases, choosing who each one is split between. The app keeps a running net balance per member, suggests who should pay whom, and lets an admin settle the room. Both a web app and an Android app consume the same backend.

For a visual walkthrough of the expense → split → balance flow, open [domain-overview.html](domain-overview.html).

---

## Core Entities

Table names are case-sensitive in Postgres — mixed-case names must be double-quoted in SQL (`"Users"`, `"Rooms"`, `"UserRooms"`, `"Spendings"`, `"SpendingSplits"`, `"RoomBalanceSummary"`, `"Invite"`). `notifications` and `fcm_tokens` are lower-case.

### Users
A registered person, created on first login (Google or Facebook — see [AUTH.md](AUTH.md)).

| Field      | Type      | Notes                                          |
|------------|-----------|------------------------------------------------|
| id         | bigint PK | Used as `sub` in the JWT and as FK everywhere new |
| uid        | varchar   | `"<provider>:<email>"`, rewritten on each login |
| email      | varchar   | Unique; still used as FK by `Spendings.user`   |
| name       | text      | Refreshed from the provider on each login      |
| profile    | text      | Avatar URL                                     |
| created_at | timestamp |                                                |

### Rooms
A shared household / group. Deliberately thin — member count and admin are **derived** from `UserRooms`, not stored.

| Field      | Type      | Notes                                    |
|------------|-----------|------------------------------------------|
| id         | bigint PK |                                          |
| uid        | varchar   | Unused by the API                        |
| name       | text      | Unused by the API                        |
| created_at | timestamp |                                          |

API responses expose `members` (count of `UserRooms` rows) and `admin` (email of one Admin of the room).

### UserRooms (membership)
Many-to-many join between Users ↔ Rooms with a role.

| Field     | Type      | Notes                   |
|-----------|-----------|-------------------------|
| id        | int PK    |                         |
| user_id   | int FK    | → Users.id              |
| room_id   | int FK    | → Rooms.id              |
| role      | text      | `Admin` or `Member`     |
| joined_at | timestamp |                         |

### Spendings (Expenses)
A purchase entry paid by one member.

| Field      | Type      | Notes                                               |
|------------|-----------|-----------------------------------------------------|
| id         | bigint PK |                                                     |
| room       | bigint FK | → Rooms.id                                          |
| user_id    | bigint FK | → Users.id — the payer                              |
| user       | text      | Payer's email (legacy column, still written and filtered on) |
| material   | text      | Item / description                                  |
| money      | bigint    | Amount spent                                        |
| created_at | timestamp | Defaults to NOW; the client may supply it           |
| settled    | bool      | NULL / false = pending, true = settled              |
| settled_at | timestamp | Set when settled. NULL on some expenses settled before this column existed — `settled` is the source of truth |

### SpendingSplits
Per-participant share of one expense. A row's existence **is** the participation record. `net` (a member's balance contribution from this expense) is **not stored**; it is computed as `amount_paid - amount_owed`.

| Field       | Type          | Notes                                                 |
|-------------|---------------|-------------------------------------------------------|
| id          | bigint PK     |                                                       |
| spending_id | bigint FK     | → Spendings.id, `ON DELETE CASCADE`                   |
| user_id     | bigint FK     | → Users.id, `ON DELETE CASCADE`                       |
| amount_paid | numeric(10,2) | Non-zero only on the payer's row (= Spendings.money)  |
| amount_owed | numeric(10,2) | Even split: `round(money / participant_count, 2)`     |
| created_at  | timestamp     |                                                       |

Unique on `(spending_id, user_id)`.

- Created with an explicit `participant_user_ids` list → only those members get a row.
- Created without one → every current room member gets a row.
- The payer gets `amount_paid` only if they are among the participants. If the payer is left out of `participant_user_ids`, no row records the payment.
- Existing rows were backfilled only for expenses that were still unsettled at migration time; older settled expenses have no splits.

### RoomBalanceSummary
A member's running net position in a room, kept as a **historical ledger**: one **active** row per `(room, user)` plus any number of **closed** rows from past settle-alls. This is what `GET /splits`, settle-all verification and the exit/remove guards read.

| Field          | Type          | Notes                                                        |
|----------------|---------------|--------------------------------------------------------------|
| id             | bigint PK     |                                                              |
| room_id        | bigint FK     | → Rooms.id, `ON DELETE CASCADE`                              |
| user_id        | bigint FK     | → Users.id, `ON DELETE CASCADE`                              |
| pending_amount | numeric(10,2) | Signed net: positive = owed to them, negative = they owe     |
| settled_at     | timestamp     | NULL = active row; set = closed settlement record            |
| updated_at     | timestamp     | Refreshed whenever the active row changes                    |

At most one row per `(room_id, user_id)` may have `settled_at IS NULL` (partial unique index `uq_room_balance_summary_active`).

- **Expense add / edit / delete** shifts the active row's `pending_amount` by the member's `net` for that expense, in the same transaction. The active row is created on demand.
- **Settle-all** stamps `settled_at = now()` on every active row in the room, freezing "this much was owed, settled at this time", then opens a fresh active row at `0` for every current member.
- "Who pays whom" is **not persisted** — it is computed on read from the active rows by greedy debt simplification (largest debtor pays largest creditor, repeat).

### Invite
One-time invite link to join a room.

| Field      | Type      | Notes                                           |
|------------|-----------|-------------------------------------------------|
| id         | bigint PK |                                                 |
| room       | bigint FK | → Rooms.id                                      |
| invited_by | int FK    | → Users.id                                      |
| token      | uuid      | Unique, used in the share URL                   |
| status     | text      | `pending` / `accepted` / `rejected` / `expired` |
| created_at | timestamp |                                                 |
| updated_at | timestamp |                                                 |

Invite expires after **7 days**.

### notifications (activity log) — routes currently unmounted
Room activity log. The table and code exist, but its router is not registered in `main.py`, so nothing writes to it today.

| Field         | Type      | Notes                                                              |
|---------------|-----------|--------------------------------------------------------------------|
| id            | int PK    |                                                                    |
| room_id       | int FK    | → Rooms.id                                                         |
| triggered_by  | int FK    | → Users.id                                                         |
| activity_type | varchar   | `payment` / `grocery` / `expense` / `member_join` / `member_leave` |
| title         | varchar   |                                                                    |
| message       | text      |                                                                    |
| data          | jsonb     | Extra metadata                                                     |
| created_at    | timestamp |                                                                    |

### fcm_tokens
A Firebase Cloud Messaging device token belonging to a user. Not room-scoped — one device receives pushes for all of its user's rooms.

| Field      | Type        | Notes                                       |
|------------|-------------|---------------------------------------------|
| id         | bigint PK   |                                             |
| user_id    | bigint FK   | → Users.id, `ON DELETE CASCADE`             |
| fcm_token  | text        | Unique                                      |
| platform   | varchar(20) | Defaults to `android`                       |
| created_at | timestamp   |                                             |
| updated_at | timestamp   |                                             |

Registering a token that already exists re-assigns it to the calling user (a second account logging in on the same device takes the token over).

### Removed
- `balance` (settlement/contribution ledger) — dropped in migration `20260718165615`; replaced by `Spendings.settled_at` and `RoomBalanceSummary`.
- `push_subscriptions` (Web Push / VAPID) — dropped in migration `20260903083333`; replaced by `fcm_tokens`.
- `SpendingParticipants` — still created by the baseline migration but never read or written; superseded by `SpendingSplits`.

---

## Business Rules

### Roles
- A room's creator becomes its first `Admin`. A room can have more than one Admin.
- An Admin cannot demote themselves, cannot remove themselves, and cannot exit the room — exiting is only open to non-admins.
- Only Admins can: add expenses for others, edit or delete expenses, change member roles, remove members, create invite links, settle the room, delete the room.
- Any member can add an expense they paid for and read everything in the room.

### Adding an expense
1. `money` must be greater than 0.
2. Resolve participants: the given `participant_user_ids` (each must be a member of the room, otherwise 400), or all current members if omitted.
3. Insert the `Spendings` row.
4. Write one `SpendingSplits` row per participant: `amount_owed = round(money / n, 2)`; `amount_paid = money` on the payer's row, `0` elsewhere.
5. Shift each participant's active `RoomBalanceSummary.pending_amount` by `amount_paid - amount_owed`.
6. Send a push to every participant except the person who added it (best-effort — see ARCHITECTURE.md).

"Add for member" (Admin) is the same flow with another member as the payer; the admin who entered it is the one excluded from the push.

Because each share is rounded to 2 decimals, the shares of an expense may not sum exactly to `money` (100 ÷ 3 → 3 × 33.33), leaving up to a few cents of drift in the room's balances.

### Editing and deleting an expense (Admin)
- Changing `money` reverses the old splits and balance shifts, then re-applies them with the **same participants and the same payer**. Participants cannot be changed after creation.
- Changing only `material` / `created_at` leaves splits untouched.
- Deleting reverses the balance shifts and removes the expense; its splits go with it.

### Balances — two different "pending" numbers
The API uses `pending_amount` for two distinct things:

| Where | Meaning |
|-------|---------|
| `GET /splits` → `members[].pending_amount`, settle-all verification, exit/remove guards | **Net balance** — the member's active `RoomBalanceSummary` row. Signed: positive = the room owes them, negative = they owe. |
| `GET /rooms/{id}` → `pending_amount`, `GET /splits` → `total_pending` | **Unsettled spend** in the room — `SUM(money)` over expenses with `settled IS NOT TRUE`. Never negative. |
| `GET /rooms/{id}/dashboard` → `members[].pending_amount`, `GET /members/{user_id}` → `pending_amount` | **Unsettled spend paid by that member.** Never negative. |

`total_spent` (room summary, member detail) is `SUM(money)` over all expenses, settled or not.

### Suggested settlements
`GET /splits` returns `settlements[]` — `{from_user_email, to_user_email, amount}` transfers that would zero the active balances. Balances within `0.01` of zero are ignored. These are suggestions for display; nothing is stored.

### Settle-all (Admin)
1. The client sends the balances it is showing: `members[] {user_email, pending_amount}`.
2. For each one, the server compares against the active `RoomBalanceSummary` row. A difference greater than **0.01** rejects the request with 400 — the client is looking at stale data.
3. Close every active `RoomBalanceSummary` row in the room (`settled_at = now()`).
4. Open a fresh active row at `0` for every current member.
5. Mark every unsettled expense in the room `settled = true, settled_at = now()`.
6. Publish an `expense_split` event with the pre-settle summary (drives the settlement email).

Settlement is all-or-nothing per room: there is no single-member settle, no partial or filtered settle, and no "contribute" (lump-sum credit). Past settlements are the closed `RoomBalanceSummary` rows; there is no endpoint that lists them yet.

### Leaving and removing members
- A member cannot exit, and an Admin cannot remove a member, while that member's net balance is non-zero — whether they owe or are owed. Settle the room first.
- Removing a membership does not touch the member's expenses or splits.

### Room Deletion (Admin)
- Blocked if **any** unsettled expenses remain.
- Delete order: `Spendings` → `Invite` → `notifications` → `UserRooms` → `Rooms`. `SpendingSplits` rows go with their `Spendings`, and `RoomBalanceSummary` rows (including history) go with the `Rooms` row, via `ON DELETE CASCADE`.

### Invite Flow
1. Admin calls `POST /rooms/{room_id}/invites` → returns a UUID token.
2. The client builds the share URL from the token (`/invite/{token}` in the web app).
3. Recipient: `GET /invites/{token}` to validate (public — works before sign-in), `POST /invites/{token}/accept` to join.
4. Token expires 7 days after creation. Expiry is checked at validate and accept time; an expired invite is marked `expired` and returns 410, as does any invite that is no longer `pending`.
5. Accept is idempotent — an existing member gets a success response and no duplicate membership.

### Side effects
| Trigger | Effect |
|---------|--------|
| First login | `welcome` event → `rg:emails` stream |
| Expense added | FCM push to the other participants |
| Settle-all | `expense_split` event → `rg:emails` stream |

All of these are best-effort and never fail the request.

---

## Relationships Diagram (simplified)

```
Users ──< UserRooms >── Rooms
Users ──< Spendings >── Rooms                (payer: user_id, plus legacy email in "user")
Spendings ──< SpendingSplits >── Users       (participants + share, per expense)
Users ──< RoomBalanceSummary >── Rooms       (one active row + N closed rows per member per room)
Users ──< Invite    >── Rooms                (invited_by)
Users ──< fcm_tokens                         (one row per device)
Rooms ──< notifications                      (activity log, unmounted)
```
