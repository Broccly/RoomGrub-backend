# RoomGrub Backend — Authentication

## Strategy: provider token in, RoomGrub JWT out

The client signs in with an identity provider (Google or Facebook) and hands
the provider's token to this backend **once**. The backend verifies it,
upserts the user, and issues **its own** HS256 JWT. Every other request is
authenticated with that RoomGrub JWT — the provider is not contacted again.

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
    ▼
{ "access_token": "<jwt>", "token_type": "bearer", "user": {...} }
    │
    │  6. All other requests: Authorization: Bearer <access_token>
    ▼
get_current_user dependency          app/dependencies/current_user.py
    │
    │  7. Verify signature + expiry with JWT_SECRET (HS256)
    │  8. Load user by id — Redis cache first, then "Users"
    ▼
Route handler receives current_user: dict  { id, email, name, profile }
```

---

## Login endpoint

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

### Provider verification

| Provider | Token expected | How it is verified |
|----------|----------------|--------------------|
| `google` | OAuth `id_token` | `google.oauth2.id_token.verify_oauth2_token` — signature, expiry and `aud == GOOGLE_CLIENT_ID`; then `iss` must be `accounts.google.com` |
| `facebook` | User access token | `GET https://graph.facebook.com/me?fields=id,name,email,picture` — must return 200 with an `email` |

Adding a provider means adding a `_verify_<name>` function returning
`{email, name, picture}` and registering it in `_PROVIDERS`.

---

## The RoomGrub JWT

Issued by `create_jwt` in `app/utils/jwt_utils.py`:

| Claim | Value |
|-------|-------|
| `sub` | `Users.id`, as a string |
| `email` | User's email |
| `exp` | now + `JWT_EXPIRY_HOURS` (default 24) |

Signed with `JWT_SECRET`, algorithm HS256. There is no refresh token and no
refresh endpoint — when the token expires the client logs in again with a
fresh provider token.

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
| None (public) | `POST /auth/login`, `GET /invites/{token}`, `GET /health` |
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

---

## Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `JWT_SECRET` | yes | HS256 signing key for RoomGrub JWTs — at least 32 random characters |
| `JWT_EXPIRY_HOURS` | no (24) | Token lifetime |
| `GOOGLE_CLIENT_ID` | yes | Expected `aud` of Google `id_token`s |
| `REDIS_URL` | yes | Auth / room-access cache and event stream |
| `CACHE_TTL_SECONDS` | no (604800) | TTL for both cache keys |

---

## Client notes (web and Android)

1. Obtain a Google `id_token` (or Facebook access token) from the provider SDK. For Google it must be issued for the same OAuth client ID as `GOOGLE_CLIENT_ID`.
2. `POST /api/v1/auth/login` and store `access_token` securely.
3. Send `Authorization: Bearer <access_token>` on every request.
4. On `401`, sign in again — there is no refresh flow.
5. After login, register the device for push with `POST /api/v1/notifications/fcm-token`; unregister it on logout.

---

## Security notes

- `JWT_SECRET` must never reach a client bundle; rotating it invalidates every issued token.
- Tokens cannot be revoked individually before `exp`.
- All access control is enforced in this service. Supabase Row Level Security is not relied on — the app connects with a direct Postgres role.
- Room-scoped routes must take `room_id` from the path and depend on a `require_room_*` guard. Trusting a `room_id` from the request body is how the notifications IDOR fixed in 1.1.0 happened.
