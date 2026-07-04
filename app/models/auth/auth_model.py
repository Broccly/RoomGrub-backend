from sqlalchemy import Connection, text


def upsert_user(conn: Connection, uid: str, email: str, name: str | None, profile: str | None) -> dict:
    row = conn.execute(
        text("""
            INSERT INTO "Users" (uid, email, name, profile)
            VALUES (:uid, :email, :name, :profile)
            ON CONFLICT (email) DO UPDATE
              SET uid = EXCLUDED.uid,
                  name = EXCLUDED.name,
                  profile = EXCLUDED.profile
            RETURNING id, uid, email, name, profile
        """),
        {"uid": uid, "email": email, "name": name, "profile": profile},
    ).fetchone()
    return dict(row._mapping)
