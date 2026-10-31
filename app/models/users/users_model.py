from sqlalchemy import Connection, text
from app.models.users.schemas import UserRow


def get_user(conn: Connection, user_id: int) -> dict | None:
    row = conn.execute(
        text('SELECT id, email, name, profile, type FROM "Users" WHERE id = :user_id'),
        {"user_id": user_id},
    ).fetchone()
    return UserRow(**row._mapping).model_dump() if row else None


def update_user_profile(
    conn: Connection,
    user_id: int,
    name: str | None,
    set_name: bool,
    profile: str | None,
    set_profile: bool,
) -> dict | None:
    # The set_* flags tell "leave unchanged" apart from "set to NULL" for profile.
    row = conn.execute(
        text("""
            UPDATE "Users"
            SET name = CASE WHEN :set_name THEN :name ELSE name END,
                profile = CASE WHEN :set_profile THEN :profile ELSE profile END
            WHERE id = :user_id
            RETURNING id, email, name, profile, type
        """),
        {"user_id": user_id, "name": name, "set_name": set_name, "profile": profile, "set_profile": set_profile},
    ).fetchone()
    return UserRow(**row._mapping).model_dump() if row else None
