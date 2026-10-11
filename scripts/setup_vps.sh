#!/usr/bin/env bash
# VPS Setup Script for Oggy Reels Bot
# Run as root on fresh Ubuntu 22.04/24.04 VPS

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

main() {
    log_info "Setting up VPS for Oggy Reels Bot"

    update_system
    install_docker
    install_dependencies
    create_user
    setup_firewall
    setup_fail2ban
    setup_unattended_upgrades
    setup_monitoring

    log_info "VPS setup complete!"
    log_warn "Reboot recommended: sudo reboot"
}

update_system() {
    log_info "Updating system packages..."
    apt-get update && apt-get upgrade -y
}

install_docker() {
    log_info "Installing Docker..."

    if command -v docker &> /dev/null; then
        log_info "Docker already installed"
        return
    fi

    # Install Docker
    curl -fsSL https://get.docker.com | sh

    # Install Docker Compose plugin
    apt-get install -y docker-compose-plugin

    # Verify
    docker --version
    docker compose version
}

install_dependencies() {
    log_info "Installing system dependencies..."

    apt-get install -y \
        curl \
        wget \
        git \
        htop \
        iotop \
        ncdu \
        jq \
        vim \
        nginx \
        certbot \
        python3-certbot-nginx \
        postgresql-client \
        redis-tools \
        ffmpeg \
        mediainfo \
        logrotate
}

create_user() {
    log_info "Creating application user..."

    if id "oggy" &>/dev/null; then
        log_info "User 'oggy' already exists"
    else
        useradd -m -s /bin/bash -G docker oggy
        log_info "Created user 'oggy'"
    fi

    # Create directories
    mkdir -p /opt/oggy-reels-bot/{data,logs,temp,certbot/conf,certbot/www}
    chown -R oggy:oggy /opt/oggy-reels-bot
}

setup_firewall() {
    log_info "Configuring UFW firewall..."

    ufw --force enable
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow ssh
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw status verbose
}

setup_fail2ban() {
    log_info "Configuring fail2ban..."

    cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5
backend = systemd

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3

[nginx-http-auth]
enabled = true
filter = nginx-http-auth
port = http,https
logpath = /var/log/nginx/error.log

[nginx-limit-req]
enabled = true
filter = nginx-limit-req
port = http,https
logpath = /var/log/nginx/error.log
maxretry = 10
EOF

    systemctl enable fail2ban
    systemctl restart fail2ban
}

setup_unattended_upgrades() {
    log_info "Configuring unattended upgrades..."

    apt-get install -y unattended-upgrades apt-listchanges

    cat > /etc/apt/apt.conf.d/50unattended-upgrades << 'EOF'
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
    "${distro_id}:${distro_codename}-updates";
    "${distro_id}ESMApps:${distro_codename}-apps-security";
    "${distro_id}ESM:${distro_codename}-infra-security";
};
Unattended-Upgrade::Package-Blacklist {
};
Unattended-Upgrade::DevRelease "false";
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
Unattended-Upgrade::Mail "";
EOF

    cat > /etc/apt/apt.conf.d/20auto-upgrades << 'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Download-Upgradeable-Packages "1";
APT::Periodic::AutocleanInterval "7";
APT::Periodic::Unattended-Upgrade "1";
EOF

    systemctl enable unattended-upgrades
    systemctl start unattended-upgrades
}

setup_monitoring() {
    log_info "Setting up basic monitoring..."

    # Logrotate for app logs
    cat > /etc/logrotate.d/oggy-reels-bot << 'EOF'
/opt/oggy-reels-bot/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 oggy oggy
    sharedscripts
    postrotate
        docker compose -f /opt/oggy-reels-bot/docker-compose.yml exec -T app kill -USR1 1 2>/dev/null || true
    endscript
}
EOF

    # Health check cron
    cat > /etc/cron.d/oggy-healthcheck << 'EOF'
# Check bot health every 5 minutes
*/5 * * * * oggy /usr/bin/curl -sf https://your-domain.com/health > /dev/null || /usr/bin/systemctl restart oggy-reels-bot
EOF

    log_warn "Update /etc/cron.d/oggy-healthcheck with your actual domain"
}

# Run main
main "$@"