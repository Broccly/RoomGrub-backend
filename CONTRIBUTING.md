# Contributing to RoomGrub Backend

First off — **thank you for being here!** Whether you're fixing a typo, reporting a bug, or building a brand-new endpoint, every contribution matters. RoomGrub is built by people like you, and we're genuinely excited to have you join us.

---

## You Belong Here

No contribution is too small. You don't need to be an expert. If something confused you, it'll confuse others — and your fix will help everyone. We welcome:

- Bug reports and fixes
- New features and API endpoints
- Performance and reliability improvements
- Documentation updates
- Test coverage improvements

This service is the API behind the [RoomGrub web app](https://github.com/sambhusankar/RoomGrub) and the RoomGrub Android app. It owns the database and all business rules.

---

## Getting Started

Everything below uses Docker for the database — no Supabase credentials needed to get started.

### Prerequisites

- **Python 3.12** (see `.python-version`)
- **Docker** (with Docker Compose)
- **[dbmate](https://github.com/amacneil/dbmate#installation)** for database migrations

### Setup

1. **Fork** [Broccly/RoomGrub-backend](https://github.com/Broccly/RoomGrub-backend) on GitHub (the *Fork* button, top right).
2. **Clone your fork** and add the original repo as `upstream` so you can pull in future changes:
   ```bash
   git clone https://github.com/<your-username>/RoomGrub-backend.git
   cd RoomGrub-backend
   git remote add upstream https://github.com/Broccly/RoomGrub-backend.git
   ```
3. **Create a virtualenv and install dependencies:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate      # .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```
4. **Copy the env file** — works out of the box, no values to look up:
   ```bash
   cp .env.example .env
   ```
   - `REDIS_URL` is a placeholder by default. The app runs fine without a reachable Redis (Redis errors fail open to Postgres), it just won't cache anything or publish email events. Fill in a real Upstash `rediss://` URL to enable them.
   - Login needs a real `GOOGLE_CLIENT_ID` (the same one the web/Android client uses).
   - Push notifications need `FIREBASE_CREDENTIALS_JSON`; they're disabled when it's empty.

   See [docs/SETUP.md](docs/SETUP.md) for every variable and how to obtain each one.
5. **Start both local Postgres containers** (dev DB + test DB):
   ```bash
   docker compose up -d
   ```
6. **Apply migrations to both:**
   ```bash
   ./scripts/migrate_dev_db.sh
   ./scripts/migrate_test_db.sh
   ```
7. **Run the dev server:**
   ```bash
   uvicorn main:app --reload --port 8000
   ```
   API docs at http://localhost:8000/docs, health check at http://localhost:8000/health.
8. **Create a branch** for your work:
   ```bash
   git checkout -b feat/your-feature-name
   ```

### Running the tests

`pytest` isn't in `requirements.txt` yet, so install it once into your virtualenv:

```bash
pip install pytest
```

Then:

```bash
pytest -v              # everything
pytest tests/unit      # unit tests only — no database needed
pytest tests/e2e       # API tests against the test-db container
```

Re-run `./scripts/migrate_test_db.sh` whenever a new migration is added. See [tests/README.md](tests/README.md) for how the suite is isolated and its fixtures.

---

## Making Changes

The full conventions live in **[AGENTS.md](AGENTS.md)** — please read it before writing code. The short version:

- **Layering:** routers handle HTTP only, services hold business logic, models run SQL. Services raise plain Python exceptions, not `HTTPException`.
- **Raw parameterized SQL only** — `text()` with bound parameters. No SQLAlchemy ORM classes, no f-string SQL.
- **Routes** live under `/api/v1` with no trailing slashes, and every route declares its auth guard.
- **Redis and Firebase are optional** — cache, events and push must fail open and never fail a request.
- **Schema changes** are dbmate migrations in `db/migrations/` — see [docs/MIGRATIONS.md](docs/MIGRATIONS.md).
- **Behaviour changes:** update the doc that describes the behaviour and add an entry under `[Unreleased]` in [CHANGELOG.md](CHANGELOG.md) in the same change.
- **API contract changes** (request/response shapes, status codes, new rules) can break the web and Android clients — call them out clearly in your PR.
- Keep changes focused — one feature or fix per pull request — and write clear, descriptive commit messages.
- Add or update tests in `tests/e2e/` or `tests/unit/` and make sure `pytest -v` passes before submitting.

---

## Submitting a Pull Request

1. Push your branch to your fork
2. Open a Pull Request against the `main` branch
3. Fill in the PR description — what you changed, why, and any impact on clients
4. A maintainer will review it as soon as possible

Don't worry if you get feedback — it's part of the process, not a rejection. We're here to collaborate, not gatekeep.

---

## Reporting Bugs

Found something broken? Please [open an issue](https://github.com/Broccly/RoomGrub-backend/issues) and include:

- What you expected to happen
- What actually happened
- Steps to reproduce it (the endpoint, request body, and response are especially helpful)
- Relevant logs or error messages

---

## Code of Conduct

Be kind. Be respectful. We're all here to build something useful together. Please read our [Code of Conduct](CODE_OF_CONDUCT.md) — harassment, discrimination, or hostile behavior of any kind will not be tolerated.

---

## Questions?

Not sure where to start? Raise an [issue](https://github.com/Broccly/RoomGrub-backend/issues) — we're happy to help you find your footing.

**Happy contributing! We're glad you're here.** 🙌
