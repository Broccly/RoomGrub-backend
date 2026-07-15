#!/usr/bin/env bash
# Applies all pending db/migrations/*.sql to the local Docker Postgres dev DB
# (docker-compose.yml's dev-db service) via dbmate. Safe to re-run any time.
#
# This targets the local dev-db container, not the Supabase dev project — see
# docs/MIGRATIONS.md if you need to apply migrations to Supabase instead.
set -euo pipefail

cd "$(dirname "$0")/.."

set -a
source .env
set +a
source scripts/db_url.sh

echo "Starting dev-db container..."
docker compose up -d dev-db
until docker exec roomgrub-dev-db pg_isready -U "$DB_USER" >/dev/null 2>&1; do
  sleep 1
done

export DATABASE_URL
DATABASE_URL="$(local_dev_database_url)"

echo "Applying migrations to dev-db..."
dbmate up

echo "Done. Dev DB is ready at localhost:${DB_PORT}/${DB_NAME}."
