# Running the test suite

Tests run against a local, disposable Docker Postgres — never against the live
Supabase database in `.env`.

## One-time setup

```bash
./scripts/migrate_test_db.sh   # starts the container and applies db/migrations/*.sql via dbmate
```

Re-run `migrate_test_db.sh` any time a new migration is added to `db/migrations/` —
it starts the container if needed and runs `dbmate up`, which only applies
pending migrations. See `docs/MIGRATIONS.md` for how to write a new migration
and apply it across dev/test/(future) prod.

`TEST_DB_*` env vars in `.env` point at the container (`localhost:55432` by default).
`conftest.py` refuses to run if they're missing, so tests can never silently fall
back to a real database.

## Isolation

Each test gets its own connection wrapped in a transaction that is always rolled
back on teardown (`conn` fixture in `tests/e2e/conftest.py`). No test writes
persist — no manual cleanup needed, and tests can run in any order without
interfering with each other.

## Fixtures

- `make_user(email, name=None, profile=None)` — upserts a `Users` row.
- `make_room(admin_user)` — creates a room with `admin_user` as Admin.
- `add_member(room_id, user, role="Member")` — adds a user to a room.
- `make_expense(room_id, user_email, money=10.0, material="test item")` — inserts an expense.
- `auth_headers(user)` — builds a Bearer token for a user dict (must include `id`, `email`).

## Notifications

The notifications router exists in `app/api/notifications/` but is **not mounted**
in `main.py` (see the comment there). Its test file is left as pre-existing,
unmodified coverage — the "unauthenticated" assertions there check for `401` but
actually receive `404` since the routes don't exist in the running app; this is a
known, pre-existing gap, not something introduced by this test suite.
