# RoomGrub Backend — Authentication

## Strategy: provider token in, RoomGrub tokens out

The client signs in with an identity provider (Google or Facebook) and hands
the provider's token to this backend **once**. The backend verifies it,
upserts the user, and issues **its own** tokens:

- an **access token** — a short-lived HS256 JWT that authenticates every API
  request, and
- a **refresh token** — a long-lived, revocable, opaque token
  whose only job is to get a new access token.

A signed-in device stays signed in. The user is never sent back to the
provider's sign-in screen just because a token aged out — the client silently
trades its refresh token for a new pair. A device is signed out only when:

- the user logs out on it,
- it has not talked to the API for `REFRESH_TOKEN_EXPIRY_DAYS` (default 90), or
- its refresh token is revoked (reuse detected, or the user row is deleted).

Supabase is used only as the Postgres host. Supabase Auth is not involved.

---

## Flow

```
Client (Web / Android)
    │
    │  1. Sign in with Google / Facebook SDK → provider token
    ▼
POST /api/v1/auth/login   { "provider": "google", "token": "<id_token>" }
    │
    │  2. verify_provider_token()      app/utils/auth_providers.py
    │  3. upsert_user()                app/models/auth/auth_model.py
    │  4. first login? → publish "welcome" event to the rg:emails stream
    │  5. create_jwt()                 app/utils/jwt_utils.py
    │  6. issue refresh token, store its hash in refresh_tokens
    ▼
{ "access_token": "<jwt>", "token_type": "bearer", "expires_in": 900,
  "refresh_token": "<opaque>", "user": {...} }
    │
    │  7. All other requests: Authorization: Bearer <access_token>
    ▼
get_current_user dependency          app/dependencies/current_user.py
    │
    │  8. Verify signature + expiry with JWT_SECRET (HS256)
    │  9. Load user by id — Redis cache first, then "Users"
    ▼
Route handler receives current_user: dict  { id, email, name, profile }

        ...access token expires → 401 "Token expired"...

POST /api/v1/auth/refresh   { "refresh_token": "<opaque>" }
    │
    │  10. look the token up by hash, check it is valid
    │  11. mark it used, issue a new refresh token in the same family
    │  12. create_jwt()
    ▼
{ "access_token": "<new jwt>", "token_type": "bearer", "expires_in": 900,
  "refresh_token": "<new opaque>" }
    │
    ▼
Client replaces both stored tokens and retries the request
```

---

## Tokens

| | Access token | Refresh token |
|---|---|---|
| Format | HS256 JWT signed with `JWT_SECRET` | Opaque random string (`secrets.token_urlsafe(48)`) |
| Claims | `sub` (`Users.id` as a string), `email`, `exp` | None |
| Lifetime | `JWT_ACCESS_EXPIRY_MINUTES` (default 15) | `REFRESH_TOKEN_EXPIRY_DAYS` (default 90), **sliding** — renewed on every refresh |
| Sent | `Authorization: Bearer` on every request | Only in the body of `/auth/refresh` and `/auth/logout` |
| Server state | None — verified by signature | One row in `refresh_tokens`; only the SHA-256 hash is stored |
| Revocable | No (expires within minutes) | Yes |

Both are produced in `app/utils/jwt_utils.py`: `create_jwt` for the access
token, `generate_refresh_token` / `hash_refresh_token` for the refresh token.
Refresh tokens never authenticate an API call, and `get_current_user` knows
nothing about them.

Refresh tokens live in Postgres, not Redis. Redis is fail-open in this
project, so keeping them there would mean a Redis outage signs every device
out.

### `refresh_tokens` table

| Column | Type | Notes |
|--------|------|-------|
| id | bigint PK | |
| user_id | bigint | FK → `"Users"(id)` `ON DELETE CASCADE` |
| token_hash | text | Unique. SHA-256 hex of the token — the raw token is never stored |
| family_id | uuid | One per login (i.e. per device session); every rotation of that login shares it |
| expires_at | timestamptz | `created_at` + `REFRESH_TOKEN_EXPIRY_DAYS` |
| used_at | timestamptz null | Set when the token is rotated; a used token is spent |
| revoked_at | timestamptz null | Set by logout or reuse detection |
| created_at | timestamptz | |

Indexes on `user_id` and `family_id`. A token is **valid** when it exists,
`used_at` and `revoked_at` are null, and `expires_at` is in the future.

---

## Endpoints

All three are public — none requires an access token, because the access
token may already be expired when they are called.

### Login

```
POST /api/v1/auth/login

{
  "provider": "google",        // "google" or "facebook", case-insensitive
  "token": "<provider token>"
}

200:
{
  "access_token": "<RoomGrub JWT>",
  "token_type": "bearer",
  "expires_in": 900,               // access token lifetime, seconds
  "refresh_token": "<opaque>",
  "user": { "id": 42, "email": "user@example.com", "name": "Full Name", "profile": "https://avatar-url" }
}
```

| Failure | Status |
|---------|--------|
| Unknown provider | 400 |
| Provider token invalid, wrong issuer/audience, or missing email | 401 |

The user row is upserted on email (`ON CONFLICT (email) DO UPDATE`), so `name`
and `profile` are refreshed from the provider on every login. `uid` is stored
as `"<provider>:<email>"`.

Every login starts a new refresh-token family, so each device has its own
session and logging out on one does not affect the others.

### Refresh

```
POST /api/v1/auth/refresh

{ "refresh_token": "<opaque>" }

200:
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 900,
  "refresh_token": "<new opaque>"  // the one that was sent is now spent
}

401  { "detail": "Invalid refresh token" }   // unknown, expired, revoked or reused — one message for all
```

Algorithm:

1. Hash the presented token and look the row up by `token_hash`. No row → 401.
2. `revoked_at` set, or `expires_at` passed → 401.
3. `used_at` set (the token was already rotated):
   - within the **30-second grace window** of `used_at` → treat as a concurrent
     retry (two tabs, a request retried after a dropped response) and continue
     to step 4 without marking anything;
   - otherwise → **reuse detected**: set `revoked_at` on every row of the
     `family_id`, return 401. Whoever holds the newer token is signed out too,
     which is the point — one of the two holders is not the user.
4. Set `used_at` on the presented row, insert a new row with the same
   `family_id` and a fresh `expires_at`, and return a new access token plus
   the new refresh token.

### Logout

```
POST /api/v1/auth/logout

{ "refresh_token": "<opaque>" }

204   // always, even for an unknown or already-revoked token
```

Revokes the whole family of the token it is given, so only that device is
signed out. The access token it was paired with keeps working until its `exp`
(at most `JWT_ACCESS_EXPIRY_MINUTES`). A sign-out-everywhere endpoint is not
part of the first version.

### Provider verification

| Provider | Token expected | How it is verified |
|----------|----------------|--------------------|
| `google` | OAuth `id_token` | `google.oauth2.id_token.verify_oauth2_token` — signature, expiry and `aud == GOOGLE_CLIENT_ID`; then `iss` must be `accounts.google.com` |
| `facebook` | User access token | `GET https://graph.facebook.com/me?fields=id,name,email,picture` — must return 200 with an `email` |

Adding a provider means adding a `_verify_<name>` function returning
`{email, name, picture}` and registering it in `_PROVIDERS`.

---

## `get_current_user`

```python
# app/dependencies/current_user.py
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    conn: Connection = Depends(db_conn),
    redis_client: redis.Redis = Depends(redis_conn),
) -> dict:
```

1. Decode the bearer token with `JWT_SECRET`. Expired → `401 Token expired`; anything else invalid → `401 Invalid token`.
2. Read `sub`. Missing → `401 Token missing subject claim`.
3. Look up `auth:user:{user_id}` in Redis. Hit → return it.
4. Miss → `SELECT id, email, name, profile FROM "Users" WHERE id = :id`. No row → `401 User not found`.
5. Cache the row and return it.

The result is a plain `dict` (`id`, `email`, `name`, `profile`) — there are no
ORM objects anywhere in this project.

`401 Token expired` is the client's cue to call `/auth/refresh`.

---

## Room-level access

Roles are **not** in the JWT. They live in `UserRooms.role` per room and are
resolved per request by the dependencies in `app/dependencies/room_access.py`.
All three read `room_id` from the path.

| Dependency | Passes when | Otherwise |
|------------|-------------|-----------|
| `require_room_member` | Caller has a `UserRooms` row for the room | `403 Not a member of this room` |
| `require_room_admin` | Member **and** role is `Admin` | `403 Admin role required` |
| `require_room_non_admin` | Member **and** role is not `Admin` | `403 Admins cannot perform this action` |

Each returns a membership dict:

```python
{"id": <UserRooms.id>, "role": "Admin" | "Member", "user": <current_user dict>}
```

Usage:

```python
@router.patch("/{room_id}/expenses/{expense_id}", response_model=ExpenseResponse)
def edit_expense(
    room_id: int,
    expense_id: int,
    body: ExpenseUpdate,
    conn: Connection = Depends(db_conn),
    membership: dict = Depends(require_room_admin),
) -> ExpenseResponse:
    return expenses_services.edit_expense(..., membership["user"])
```

`require_room_member` is cache-aside on `access:{user_id}:{room_id}`.

---

## Which routes need what

Auth is declared per route, not globally in `main.py`.

| Guard | Routes |
|-------|--------|
| None (public) | `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `GET /invites/{token}`, `GET /health` |
| `get_current_user` | `GET` / `POST /rooms`, `POST /invites/{token}/accept`, `POST /invites/{token}/reject`, `POST` / `DELETE /notifications/fcm-token` |
| `require_room_member` | Room summary and dashboard, list/add/get expenses, list/get members, `GET /splits` |
| `require_room_admin` | Delete room, edit/delete expense, add expense for member, change role, remove member, create invite, settle-all |
| `require_room_non_admin` | `DELETE /rooms/{room_id}/members/me` (exit room) |

`GET /invites/{token}` is deliberately public so the invite landing page can
render before the recipient has signed in.

---

## Caching

Both lookups are cached in Redis with a 7-day TTL (`CACHE_TTL_SECONDS`):

| Key | Value | Invalidated on |
|-----|-------|----------------|
| `auth:user:{user_id}` | `{id, email, name, profile}` | Nothing — expires by TTL only |
| `access:{user_id}:{room_id}` | `{id, role}` | Invite accept, role change, member remove, room exit, room delete |

Redis is fail-open: any error falls through to Postgres, and a circuit breaker
skips Redis for 30 seconds after a failure. See the Caching Layer section of
[ARCHITECTURE.md](ARCHITECTURE.md).

Because `auth:user:{id}` is never invalidated, a name or avatar change picked
up at login is not reflected in `current_user` until the cached entry expires
(tracked in [TODOS.md](TODOS.md)).

Refresh tokens are not cached — every `/auth/refresh` reads and writes
Postgres.

---

## Implementation notes

- **Layering.** SQL in `app/models/auth/auth_model.py`, row validators in
  `app/models/auth/schemas.py`, logic in `app/services/auth/auth_services.py`
  (`login`, `refresh`, `logout`). The service raises the plain
  `InvalidRefreshTokenError`; the router turns it into the 401.
- **The reuse revocation must survive the 401.** `db_conn()` rolls the
  transaction back when the request errors, so "revoke the family, then raise
  `HTTPException`" would undo the revocation. `refresh_endpoint` therefore
  **returns** a 401 `JSONResponse` instead of raising, and the request commits
  normally. Don't "tidy" this into a `raise` —
  `test_family_revocation_survives_the_401` exists to catch that.
- **Row lock.** `get_refresh_token_for_update` selects `FOR UPDATE`, so two
  requests presenting the same token are processed one after the other and the
  second one sees `used_at` set.
- **Lookup by hash.** Raw tokens are never stored or compared.
- **Housekeeping.** Every login deletes that user's expired and revoked rows
  (`delete_dead_refresh_tokens`). Spent-but-unexpired rows are kept on
  purpose: they are what lets a replay be recognised. Rows of users who never
  log in again are only removed with the user (`ON DELETE CASCADE`).

---

## Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `JWT_SECRET` | yes | HS256 signing key for access tokens — at least 32 random characters |
| `JWT_ACCESS_EXPIRY_MINUTES` | no (15) | Access token lifetime. Replaced `JWT_EXPIRY_HOURS`, which is no longer read |
| `REFRESH_TOKEN_EXPIRY_DAYS` | no (90) | Idle window: how long a device can go without refreshing before it is signed out |
| `GOOGLE_CLIENT_ID` | yes | Expected `aud` of Google `id_token`s |
| `REDIS_URL` | yes | Auth / room-access cache and event stream |
| `CACHE_TTL_SECONDS` | no (604800) | TTL for both cache keys |

---

## Client notes (web and Android)

1. Obtain a Google `id_token` (or Facebook access token) from the provider SDK. For Google it must be issued for the same OAuth client ID as `GOOGLE_CLIENT_ID`.
2. `POST /api/v1/auth/login` and store both tokens. The refresh token goes in secure storage only — Android Keystore-backed storage; on web, an httpOnly cookie owned by the Next.js server, never `localStorage`. The backend stays body-based so both clients use one flow.
3. Send `Authorization: Bearer <access_token>` on every request.
4. On `401 Token expired` (or shortly before `expires_in` runs out), call `/auth/refresh`, **replace both stored tokens**, and retry the request once.
5. Run only one refresh at a time — queue other requests behind it. Parallel refreshes with the same token are what the grace window is for, not a pattern to rely on.
6. If `/auth/refresh` returns 401, the session is over: clear both tokens and show the sign-in screen. This is the only path back to provider sign-in.
7. After login, register the device for push with `POST /api/v1/notifications/fcm-token`.
8. On logout, call `/auth/logout` with the refresh token, unregister the FCM token, then clear local storage.

---

## Security notes

- `JWT_SECRET` must never reach a client bundle. Rotating it invalidates every access token; devices recover on their next refresh rather than being signed out.
- Access tokens cannot be revoked individually — their short lifetime is the control. Revocation happens at the refresh token: logout, reuse detection, or deleting the user.
- Refresh tokens are stored only as SHA-256 hashes, so a database leak does not yield usable tokens.
- A refresh token is single-use. Replaying a spent one outside the grace window revokes that device's whole family.
- All access control is enforced in this service. Supabase Row Level Security is not relied on — the app connects with a direct Postgres role.
- Room-scoped routes must take `room_id` from the path and depend on a `require_room_*` guard. Trusting a `room_id` from the request body is how the notifications IDOR fixed in 1.1.0 happened.
