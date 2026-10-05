# Running the test suite

```bash
pytest -v              # everything
pytest tests/unit      # unit tests only — no database needed
pytest tests/e2e       # API tests
```

## Layout

- `tests/e2e/` — API tests through FastAPI's `TestClient`, one file per domain, against a real Postgres.
- `tests/unit/` — pure unit tests with external calls monkeypatched: `test_auth_providers.py` (Google token verification) and `test_push_service.py` (FCM send, dead-token pruning, never-raises).

The e2e tests run against a local, disposable Docker Postgres — never against the live
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

## Redis

`test_client` overrides `redis_conn` with an in-memory `FakeRedis` (`tests/e2e/conftest.py`)
that supports `get` / `setex` / `delete` for the auth cache and `xadd` for events. No live
Redis is needed. Request the `fake_redis` fixture to assert on published events —
`fake_redis.streams["rg:emails"]` holds every entry published during the test.

## Push

`FIREBASE_CREDENTIALS_JSON` is not needed. e2e tests that cover push monkeypatch
`send_push`; `tests/unit/test_push_service.py` fakes the Firebase client.

## Fixtures

- `make_user(email, name=None, profile=None)` — upserts a `Users` row.
- `make_room(admin_user)` — creates a room with `admin_user` as Admin.
- `add_member(room_id, user, role="Member")` — adds a user to a room.
- `make_expense(room_id, user_email, money=10.0, material="test item")` — inserts an expense, splits it evenly across the room's current members, and updates their balances.
- `auth_headers(user)` — builds a Bearer token for a user dict (must include `id`, `email`). A plain function, imported from `conftest`, not a fixture.
- `fake_redis` — the in-memory Redis the app is using for this test.

## Notifications

`main.py` mounts only the push router (`POST` / `DELETE /api/v1/notifications/fcm-token`).
The room-scoped activity-log router (`/api/v1/rooms/{room_id}/notifications`) exists in
`app/api/notifications/` but is **not mounted**.

`tests/e2e/test_notifications.py` predates both facts: it targets the unmounted
activity-log routes and the removed `/push-subscriptions` routes, so it does not reflect
the running app. Rewriting it against the `fcm-token` endpoints is tracked in
`docs/TODOS.md`.
