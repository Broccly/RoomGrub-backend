#!/usr/bin/env bash
# Builds a postgresql:// DATABASE_URL for dbmate from the *_DB_* vars in .env.
# Usage: source this file, then call the function for the target environment.
set -euo pipefail

test_database_url() {
  echo "postgresql://${TEST_DB_USER}:${TEST_DB_PASSWORD}@${TEST_DB_HOST}:${TEST_DB_PORT}/${TEST_DB_NAME}?sslmode=disable"
}

# Contributor's local Docker dev DB (docker-compose.yml's dev-db service, default
# setup from .env.example) — reads the same DB_* vars as dev_database_url below,
# but assumes a plain local Postgres with no SSL.
local_dev_database_url() {
  echo "postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}?sslmode=disable"
}

# The real Supabase dev project (only relevant if your .env's DB_* vars have been
# pointed at Supabase instead of the local dev-db container — see docs/MIGRATIONS.md).
dev_database_url() {
  echo "postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}?sslmode=require"
}
