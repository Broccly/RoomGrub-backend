#!/usr/bin/env bash
# Applies all pending db/migrations/*.sql to the local Docker Postgres test DB
# (docker-compose.yml's test-db service) via dbmate. Safe to re-run any time.
set -euo pipefail

cd "$(dirname "$0")/.."

set -a
source .env
set +a
source scripts/db_url.sh

echo "Starting test-db container..."
docker compose up -d test-db
until docker exec roomgrub-test-db pg_isready -U "$TEST_DB_USER" >/dev/null 2>&1; do
  sleep 1
done

export DATABASE_URL
DATABASE_URL="$(test_database_url)"

echo "Applying migrations to test-db..."
dbmate up

echo "Done. Test DB is ready at localhost:${TEST_DB_PORT}/${TEST_DB_NAME}."
