from datetime import datetime
from uuid import UUID
from sqlalchemy import Connection, text
from app.models.auth.schemas import RefreshTokenRow, UpsertUserRow


def upsert_user(conn: Connection, uid: str, email: str, name: str | None, profile: str | None) -> dict:
    row = conn.execute(
        text("""
            INSERT INTO "Users" (uid, email, name, profile)
            VALUES (:uid, :email, :name, :profile)
            ON CONFLICT (email) DO UPDATE
              SET uid = EXCLUDED.uid,
                  name = EXCLUDED.name,
                  profile = EXCLUDED.profile
            RETURNING id, uid, email, name, profile, (xmax = 0) as inserted
        """),
        {"uid": uid, "email": email, "name": name, "profile": profile},
    ).fetchone()
    return UpsertUserRow(**row._mapping).model_dump()


def insert_refresh_token(
    conn: Connection, user_id: int, token_hash: str, family_id: UUID, expires_at: datetime
) -> None:
    conn.execute(
        text("""
            INSERT INTO refresh_tokens (user_id, token_hash, family_id, expires_at)
            VALUES (:user_id, :token_hash, :family_id, :expires_at)
        """),
        {"user_id": user_id, "token_hash": token_hash, "family_id": family_id, "expires_at": expires_at},
    )


def get_refresh_token_for_update(conn: Connection, token_hash: str) -> dict | None:
    # Row lock: two requests presenting the same token are handled one after the other.
    row = conn.execute(
        text("""
            SELECT rt.id, rt.user_id, u.email, rt.family_id, rt.expires_at, rt.used_at, rt.revoked_at
            FROM refresh_tokens rt
            JOIN "Users" u ON u.id = rt.user_id
            WHERE rt.token_hash = :token_hash
            FOR UPDATE OF rt
        """),
        {"token_hash": token_hash},
    ).fetchone()
    return RefreshTokenRow(**row._mapping).model_dump() if row else None


def mark_refresh_token_used(conn: Connection, token_id: int, used_at: datetime) -> None:
    conn.execute(
        text("UPDATE refresh_tokens SET used_at = :used_at WHERE id = :id"),
        {"id": token_id, "used_at": used_at},
    )


def revoke_refresh_token_family(conn: Connection, family_id: UUID, revoked_at: datetime) -> None:
    conn.execute(
        text("""
            UPDATE refresh_tokens
            SET revoked_at = :revoked_at
            WHERE family_id = :family_id AND revoked_at IS NULL
        """),
        {"family_id": family_id, "revoked_at": revoked_at},
    )


def delete_dead_refresh_tokens(conn: Connection, user_id: int, now: datetime) -> None:
    # Spent-but-unexpired rows are kept: reuse detection needs them to recognise a replay.
    conn.execute(
        text("""
            DELETE FROM refresh_tokens
            WHERE user_id = :user_id AND (expires_at <= :now OR revoked_at IS NOT NULL)
        """),
        {"user_id": user_id, "now": now},
    )
