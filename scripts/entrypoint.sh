#!/usr/bin/env bash
# Docker entrypoint script

set -euo pipefail

echo "Starting Oggy Reels Bot..."

# Wait for database
echo "Waiting for database..."
until pg_isready -h "${DB_HOST:-postgres}" -p "${DB_PORT:-5432}" -U "${DB_USER:-oggy}" > /dev/null 2>&1; do
    sleep 2
done
echo "Database ready!"

# Wait for Redis
echo "Waiting for Redis..."
until redis-cli -h "${REDIS_HOST:-redis}" -p "${REDIS_PORT:-6379}" ping > /dev/null 2>&1; do
    sleep 2
done
echo "Redis ready!"

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Initialize database tables if needed
echo "Initializing database..."
python scripts/init_db.py

echo "Starting application..."
exec "$@"