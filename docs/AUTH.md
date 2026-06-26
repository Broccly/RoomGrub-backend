# RoomGrub Backend — Authentication

## Strategy: Supabase JWT Verification

RoomGrub uses **Supabase Auth** as the identity provider. Users authenticate with Google OAuth (or email/password) via the Supabase client on the frontend. The FastAPI backend **does not issue tokens** — it only verifies the JWTs that Supabase issues.

---

## Flow

```
Client (Web / Android)
    │
    │  1. Login via Supabase Auth SDK (Google OAuth)
    ▼
Supabase Auth
    │
    │  2. Returns access_token (JWT) + refresh_token
    ▼
Client stores token
    │
    │  3. All API requests: Authorization: Bearer <access_token>
    ▼
FastAPI get_current_user dependency
    │
    │  4. Verify JWT signature using Supabase JWT secret (HS256)
    │     OR via Supabase JWKS endpoint (RS256 for newer projects)
    ▼
    │  5. Extract: sub (uid), email, user_metadata
    ▼
    │  6. Look up Users table by email
    │     → If not found: return 401 (user must call /auth/sync-user first)
    ▼
    Route handler receives: current_user (User ORM model)
```

---

## JWT Verification

Supabase JWTs are signed with your project's `JWT_SECRET` (HS256 by default).

```python
# app/dependencies/auth.py
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings

bearer_scheme = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    email = payload.get("email")
    uid = payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Token missing email claim")

    user = await db.scalar(select(User).where(User.email == email))
    if not user:
        raise HTTPException(status_code=401, detail="User not registered. Call /auth/sync-user.")

    return user
```

---

## User Sync Endpoint

The very first time a user logs in, the frontend calls `/auth/sync-user` to upsert the user record into the `Users` table (populated from JWT claims).

```
POST /auth/sync-user
Authorization: Bearer <supabase_access_token>

Response 200:
{
  "id": 42,
  "uid": "uuid-from-supabase",
  "email": "user@example.com",
  "name": "Full Name",
  "profile": "https://avatar-url"
}
```

This replaces the implicit user creation that happened in the Next.js Supabase callback route.

---

## Role-Based Access (Room Level)

Roles are **not** in the JWT. They are stored in `UserRooms.role` per room. Authorization is checked at the service layer on each operation.

Reusable FastAPI dependencies:

```python
# app/dependencies/room_access.py

async def require_room_member(
    room_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserRoom:
    membership = await get_membership(db, current_user.id, room_id)
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this room")
    return membership

async def require_room_admin(
    membership: UserRoom = Depends(require_room_member),
) -> UserRoom:
    if membership.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return membership
```

Usage in routes:

```python
@router.post("/rooms/{room_id}/invites")
async def create_invite(
    room_id: int,
    membership: UserRoom = Depends(require_room_admin),
    db: AsyncSession = Depends(get_db),
):
    ...
```

---

## Environment Variables

```env
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_JWT_SECRET=your-supabase-jwt-secret       # From Supabase project settings → API → JWT Secret
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key    # Only if you need admin DB access outside RLS
DATABASE_URL=postgresql+asyncpg://user:pass@db.supabase.co:5432/postgres
```

The `SUPABASE_JWT_SECRET` is found in **Supabase Dashboard → Project Settings → API → JWT Settings → JWT Secret**.

---

## Android App Considerations

The Android app (React Native / `RoomGrub-native`) should:
1. Use the Supabase JS/React Native SDK to authenticate.
2. Store the `access_token` securely (e.g., `react-native-keychain` or `expo-secure-store`).
3. Refresh the token using `supabase.auth.refreshSession()` before it expires (default 1 hour).
4. Send `Authorization: Bearer <token>` on every API call to this FastAPI backend.

Token refresh is handled entirely client-side — the FastAPI backend is stateless.

---

## Security Notes

- Always validate `aud: "authenticated"` claim to prevent tokens from other Supabase projects being accepted.
- The `SUPABASE_JWT_SECRET` must never be exposed in client bundles.
- RLS (Row Level Security) in Supabase is bypassed when connecting directly via SQLAlchemy with the service role key — enforce all access rules at the FastAPI service layer instead.
