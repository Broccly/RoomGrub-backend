# RoomGrub Backend

Standalone **Python FastAPI** backend for RoomGrub — a shared-expense tracker for roommates. Extracted from the RoomGrub Next.js monolith to serve both the web app and the Android app via a single REST API.

## What it does

- Rooms: create and manage shared household groups
- Expenses: log purchases, track who spent what
- Splits: choose who shares each expense, keep a running net balance per member, suggest who pays whom, settle the room
- Members: manage roles (Admin / Member), invite via link
- Push: Firebase Cloud Messaging to an expense's participants
- Events: welcome and settlement emails via a Redis stream

## Tech stack

- **FastAPI** — REST API framework
- **PostgreSQL** (Supabase-hosted in dev/prod; local Docker Postgres for local dev/test) — schema managed via [dbmate](https://github.com/amacneil/dbmate) migrations
- **Raw SQL** — all DB queries are parameterized SQL, no ORM
- **Auth** — Google / Facebook token exchanged at login for an app-issued short-lived access JWT (verified on every request) plus a rotating refresh token that clients can use to keep devices signed in
- **Redis (Upstash)** — cache-aside layer for auth/room-access checks (fails open to Postgres if unreachable) and the `rg:emails` event stream
- **Firebase Cloud Messaging** — push notifications (optional; disabled when unconfigured)
- **Pydantic v2** — request/response validation

## Running it locally

Want to run the backend locally or contribute? See **[CONTRIBUTING.md](CONTRIBUTING.md)** — it covers prerequisites, setup, migrations, running the server and the test suite.

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, project structure, API surface |
| [docs/DOMAIN.md](docs/DOMAIN.md) | Entity model, business rules, relationships |
| [docs/AUTH.md](docs/AUTH.md) | Login, access + refresh tokens, role guards |
| [docs/SETUP.md](docs/SETUP.md) | Env var reference, Google / Redis / Firebase setup |
| [docs/PLAN.md](docs/PLAN.md) | Project status by phase, what's next |
| [docs/TODOS.md](docs/TODOS.md) | Open work and shipped checklist |
| [docs/MIGRATIONS.md](docs/MIGRATIONS.md) | Writing and applying dbmate migrations |
| [tests/README.md](tests/README.md) | Test suite setup, isolation, fixtures |
| [AGENTS.md](AGENTS.md) | Conventions for contributors and AI agents (`CLAUDE.md` is a symlink to it) |
| [CHANGELOG.md](CHANGELOG.md) | Release history |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Local setup, tests, and how to submit changes |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | Community standards |
| [LICENSE](LICENSE) | MIT license |

## Project structure

```
main.py               # App entry point
app/
  api/<domain>/       # Route handlers + Pydantic schemas
  models/<domain>/    # Raw SQL query functions
  services/<domain>/  # Business logic
  dependencies/       # FastAPI DI: auth, room access guards
  cache/
    auth_cache.py     # Cache-aside helpers for auth/room-access (fail-open, circuit breaker)
  events/
    publisher.py      # publish_event → Redis stream rg:emails
  utils/              # Provider token verification, JWT creation
db/
  config.py           # Env var getters
  engine.py           # SQLAlchemy connection engine + db_conn()
  redis_client.py     # Redis client singleton + redis_conn()
  redis_circuit.py    # In-process circuit breaker for Redis outages
  migrations/         # dbmate migrations
scripts/              # Migration helper scripts
docs/                 # All documentation
tests/
  e2e/                # API tests against the test-db container
  unit/               # Unit tests
```

## License

[MIT](LICENSE)
