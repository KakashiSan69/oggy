#!/usr/bin/env bash
# Development environment setup script

set -euo pipefail

echo "Setting up development environment for Oggy Reels Bot..."

# Check if docker is available
if ! command -v docker &> /dev/null; then
    echo "Docker not found. Please install Docker first."
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "Docker Compose v2 not found. Please install Docker Compose plugin."
    exit 1
fi

# Copy environment file if not exists
if [[ ! -f .env ]]; then
    if [[ -f .env.example ]]; then
        cp .env.example .env
        echo "Created .env from .env.example"
        echo "Please edit .env with your credentials"
    else
        echo ".env.example not found"
        exit 1
    fi
fi

# Build and start services
echo "Building Docker images..."
docker compose -f docker-compose.yml -f docker-compose.override.yml build

echo "Starting services..."
docker compose -f docker-compose.yml -f docker-compose.override.yml up -d

# Wait for services
echo "Waiting for services to be ready..."
sleep 10

# Run database initialization
echo "Initializing database..."
docker compose -f docker-compose.yml -f docker-compose.override.yml exec -T app python scripts/init_db.py

echo ""
echo "Development environment ready!"
echo ""
echo "Services:"
echo "  - API: http://localhost:8000"
echo "  - API Docs: http://localhost:8000/docs"
echo "  - pgAdmin: http://localhost:5050 (admin@local.dev / admin)"
echo "  - Redis Commander: http://localhost:8081"
echo ""
echo "Useful commands:"
echo "  make logs        # Follow logs"
echo "  make shell       # Open shell in app container"
echo "  make test        # Run tests"
echo "  make lint        # Run linter"
echo "  make format      # Format code"
echo "  make down        # Stop services"