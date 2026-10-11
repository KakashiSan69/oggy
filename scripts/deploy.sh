#!/usr/bin/env bash
# Deployment script for Oggy Reels Bot
# Run on your VPS after cloning the repository

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Configuration
REPO_DIR="${REPO_DIR:-/opt/oggy-reels-bot}"
DOMAIN="${DOMAIN:-your-domain.com}"
EMAIL="${EMAIL:-admin@your-domain.com}"

main() {
    log_info "Starting deployment of Oggy Reels Bot"

    # Check prerequisites
    check_prerequisites

    # Setup directory
    setup_directory

    # Configure environment
    configure_env

    # Setup SSL
    setup_ssl

    # Deploy with Docker Compose
    deploy_docker

    # Verify deployment
    verify_deployment

    log_info "Deployment complete!"
    log_info "Access your bot at: https://$DOMAIN"
    log_info "Health check: https://$DOMAIN/health"
    log_info "API docs: https://$DOMAIN/docs"
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    for cmd in docker docker-compose curl openssl; do
        if ! command -v "$cmd" &> /dev/null; then
            log_error "$cmd is not installed"
            exit 1
        fi
    done

    # Check Docker Compose version
    if ! docker compose version &> /dev/null; then
        log_error "Docker Compose v2 required"
        exit 1
    fi

    log_info "Prerequisites OK"
}

setup_directory() {
    log_info "Setting up directory: $REPO_DIR"
    sudo mkdir -p "$REPO_DIR"
    sudo chown "$USER:$USER" "$REPO_DIR"
    cd "$REPO_DIR"
}

configure_env() {
    log_info "Configuring environment..."

    if [[ ! -f .env ]]; then
        if [[ -f .env.example ]]; then
            cp .env.example .env
            log_warn "Created .env from .env.example - YOU MUST EDIT IT!"
            log_warn "Run: nano .env"
            read -p "Press Enter after editing .env..."
        else
            log_error ".env.example not found"
            exit 1
        fi
    fi

    # Validate required variables
    source .env
    required_vars=(
        "YOUTUBE_API_KEY"
        "YOUTUBE_CHANNEL_IDS"
        "IG_APP_ID"
        "IG_APP_SECRET"
        "IG_ACCESS_TOKEN"
        "IG_USER_ID"
        "IG_PAGE_ID"
        "LLM_API_KEY"
        "STORAGE_ENDPOINT"
        "STORAGE_ACCESS_KEY"
        "STORAGE_SECRET_KEY"
        "STORAGE_BUCKET"
        "STORAGE_PUBLIC_URL"
        "DB_PASSWORD"
    )

    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" || "${!var}" == "changeme_secure_password_here" ]]; then
            log_error "Required variable $var is not set in .env"
            exit 1
        fi
    done

    log_info "Environment configured"
}

setup_ssl() {
    log_info "Setting up SSL certificates..."

    # Create certbot directories
    mkdir -p certbot/conf certbot/www

    # Check if certs exist
    if [[ ! -d "certbot/conf/live/$DOMAIN" ]]; then
        log_info "Requesting Let's Encrypt certificate for $DOMAIN..."
        docker run --rm \
            -v "$PWD/certbot/conf:/etc/letsencrypt" \
            -v "$PWD/certbot/www:/var/www/certbot" \
            certbot/certbot certonly \
            --webroot -w /var/www/certbot \
            -d "$DOMAIN" \
            --email "$EMAIL" \
            --agree-tos --no-eff-email --non-interactive
    else
        log_info "Certificates already exist"
    fi

    # Update nginx.conf with domain
    sed -i "s/your-domain.com/$DOMAIN/g" nginx.conf
}

deploy_docker() {
    log_info "Deploying with Docker Compose..."

    # Pull latest images
    docker compose pull

    # Build app image
    docker compose build --no-cache app

    # Start services
    docker compose up -d

    # Wait for services to be healthy
    log_info "Waiting for services to start..."
    sleep 10

    # Run database migrations
    docker compose exec -T app python -m src.db.init_db 2>/dev/null || true
}

verify_deployment() {
    log_info "Verifying deployment..."

    local max_attempts=30
    local attempt=0

    while [[ $attempt -lt $max_attempts ]]; do
        if curl -sf "https://$DOMAIN/health" > /dev/null; then
            log_info "Health check passed!"
            return 0
        fi
        attempt=$((attempt + 1))
        log_info "Waiting for health check... ($attempt/$max_attempts)"
        sleep 2
    done

    log_error "Health check failed after $max_attempts attempts"
    log_error "Check logs: docker compose logs app"
    exit 1
}

# Run main
main "$@"