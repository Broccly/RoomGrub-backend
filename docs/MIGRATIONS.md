# Database migrations (dbmate)

Schema changes are managed with [dbmate](https://github.com/amacneil/dbmate) —
plain versioned SQL files in `db/migrations/`, applied the same way to every
environment via a `DATABASE_URL`.

## Environments

| Environment | Source of `DATABASE_URL` | Status |
|---|---|---|
| test | `TEST_DB_*` vars in `.env` (local Docker Postgres, `docker-compose.yml`'s `test-db`) | active |
| local dev | `DB_*` vars in `.env` (local Docker Postgres, `docker-compose.yml`'s `dev-db` — the default from `.env.example`) | active |
| Supabase dev | the *same* `DB_*` vars, if you've personally pointed `.env` at the real Supabase dev project instead of the local container | active, adopted manually (see below) |
| prod | not provisioned yet | follow the same pattern once it exists |

`scripts/db_url.sh` builds the URL from those vars — source it and call the
function you need: `test_database_url`, `local_dev_database_url` (local
Docker dev-db, `sslmode=disable`), or `dev_database_url` (Supabase,
`sslmode=require` — only relevant if your own `.env` points there).

## Applying migrations

**Test** and **local dev** (safe to run any time — disposable containers):

```bash
./scripts/migrate_test_db.sh
./scripts/migrate_dev_db.sh
```

**Supabase dev** (only if your `.env`'s `DB_*` vars point at Supabase instead
of the local `dev-db` container — run manually once you've verified against
test):

```bash
set -a; source .env; set +a
source scripts/db_url.sh
export DATABASE_URL="$(dev_database_url)"
dbmate up
```

**Prod**: once a prod Supabase project exists, add `PROD_DB_*` vars to `.env`,
add a `prod_database_url` function to `scripts/db_url.sh`, and apply the same way.

## Writing a new migration

```bash
dbmate new add_some_column
# edit the generated db/migrations/<timestamp>_add_some_column.sql,
# filling in -- migrate:up and -- migrate:down
./scripts/migrate_test_db.sh   # verify against test first
./scripts/migrate_dev_db.sh    # then your local dev DB
# then apply to Supabase dev / prod the same way once verified, if applicable
```

## After applying a migration

- Update `docs/DOMAIN.md` if tables or columns changed, and add the migration to the history table below.
- Add a `CHANGELOG.md` entry.
- `db/schema.sql` is a committed schema dump. It is currently stale (see `docs/TODOS.md`); don't treat it as the source of truth — the migrations are.

## Migration history

| Version | File | What it does |
|---------|------|--------------|
| `20260715161501` | `baseline_schema` | Schema as it existed in Supabase dev when dbmate was adopted |
| `20260718165615` | `fold_settlements_into_spendings` | Adds `Spendings.user_id` and `Spendings.settled_at`, backfills them, drops `balance` |
| `20260722120000` | `add_spending_splits_and_balance_summary` | Creates `SpendingSplits` and `RoomBalanceSummary`, backfills both |
| `20260724120000` | `fix_room_balance_summary_backfill` | Recomputes balances the previous backfill missed (`settled IS NULL` expenses). Data only; no-op down |
| `20260724130000` | `rebuild_room_balance_from_pending` | Wipes and rebuilds splits and balances from unsettled expenses, always including the payer. Data only |
| `20260903083333` | `replace_push_subscriptions_with_fcm_tokens` | Drops `push_subscriptions`, creates `fcm_tokens` |
| `20261005120000` | `add_refresh_tokens` | Creates `refresh_tokens` (hashed, rotating refresh tokens — see AUTH.md) |

Two of these are destructive on the way up and only best-effort on the way down: `20260718165615` discards lump-sum `balance` rows, and `20260903083333` discards all Web Push subscriptions.

## Baseline migration

`db/migrations/20260715161501_baseline_schema.sql` captures the schema as it
existed in the dev Supabase project at the time dbmate was adopted (all 9
tables: `Invite`, `Users`, `Rooms`, `SpendingParticipants`, `Spendings`,
`UserRooms`, `balance`, `notifications`, `push_subscriptions`).

That list is a snapshot of the starting point, not the current schema — `balance`
and `push_subscriptions` have since been dropped and `SpendingSplits`,
`RoomBalanceSummary`, `fcm_tokens` and `refresh_tokens` added by the migrations above.

It deliberately excludes Supabase's Row Level Security policies and grants to
`authenticated`/`anon`/`service_role` — those are a Supabase platform feature
tied to Supabase-managed roles, not part of the app's own schema, and don't
apply to the local Postgres test container.

### Adopting dbmate on dev without re-running the baseline

Dev's tables already existed before dbmate, created outside any migration
tool. Running `dbmate up` there would try to `CREATE TABLE` on top of them and
fail. Instead, mark the baseline as already applied (creates dbmate's
tracking table and records one row — no schema changes):

```bash
set -a; source .env; set +a
source scripts/db_url.sh
export DATABASE_URL="$(dev_database_url)"
dbmate up   # creates schema_migrations (safe, additive)
psql "$DATABASE_URL" -c "INSERT INTO schema_migrations (version) VALUES ('20260715161501');"
```

From then on, only new migrations run against dev.
