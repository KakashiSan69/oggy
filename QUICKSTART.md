# Quick Start Guide

## 1. Prerequisites
- VPS: Ubuntu 22.04/24.04, 2 vCPU, 4GB RAM, 50GB SSD
- Domain name pointing to VPS IP
- Docker & Docker Compose v2 installed

## 2. One-Line VPS Setup (run as root)
```bash
curl -fsSL https://raw.githubusercontent.com/your-repo/oggy-reels-bot/main/scripts/setup_vps.sh | bash
```

## 3. Deploy Application
```bash
# On VPS as oggy user
cd /opt/oggy-reels-bot
git clone <your-repo> .
cp .env.example .env
nano .env  # Fill in all credentials
./scripts/deploy.sh
```

## 4. Required Credentials Checklist

| Service | What You Need |
|---------|---------------|
| YouTube | Data API v3 Key, Channel IDs |
| Instagram | Business/Creator Account, FB Page, Meta App |
| LLM | OpenAI/Anthropic API Key (or Ollama) |
| Storage | Cloudflare R2 / AWS S3 bucket + credentials |

## 5. Get Instagram Access Token
```bash
# 1. Get short token from Graph Explorer
# 2. Exchange for long-lived (60 days):
curl -X GET "https://graph.facebook.com/v20.0/oauth/access_token?\
grant_type=fb_exchange_token&\
client_id={APP_ID}&\
client_secret={APP_SECRET}&\
fb_exchange_token={SHORT_TOKEN}"

# 3. Put in .env as IG_ACCESS_TOKEN
```

## 6. Verify Deployment
```bash
# Health check
curl https://your-domain.com/health

# View stats
curl https://your-domain.com/stats

# View jobs
curl https://your-domain.com/jobs

# Manual triggers
curl -X POST https://your-domain.com/discovery/run
curl -X POST https://your-domain.com/publish/run
```

## 7. Key Configuration (.env)

```bash
# Scheduling (cron expressions, UTC)
DISCOVERY_SCHEDULE=0 */6 * * *      # Every 6 hours
POSTING_SCHEDULE=0 9,14,19 * * *    # 9AM, 2PM, 7PM UTC
CLEANUP_SCHEDULE=0 3 * * *          # Daily 3AM

# Processing
CLIPS_PER_SOURCE=3
CLIP_MIN_DURATION=15
CLIP_MAX_DURATION=60
VIDEO_CRF=22

# Limits
MAX_POSTS_PER_DAY=3
MIN_HOURS_BETWEEN_POSTS=4
```

## 8. Monitoring Commands
```bash
# Follow logs
docker compose logs -f app

# Check container status
docker compose ps

# Database shell
docker compose exec postgres psql -U oggy -d oggy_bot

# Run CLI tool
docker compose exec app python scripts/cli.py status

# Restart
docker compose restart app
```

## 9. Troubleshooting

| Issue | Solution |
|-------|----------|
| "Video processing failed" | Check video codec (H.264), public HTTPS URL, <100MB |
| "Quota exceeded" | Reduce discovery frequency, use RSS fallback |
| Posts not publishing | Check token expiry (60 days), daily limits |
| High memory | Lower CLIPS_PER_SOURCE, increase VIDEO_CRF |
| SSL issues | Re-run certbot, check nginx config |

## 10. Project Structure
```
oggy-reels-bot/
├── docker-compose.yml          # Production services
├── docker-compose.override.yml # Development services
├── Dockerfile                  # Multi-stage build
├── nginx.conf                  # Reverse proxy + SSL
├── .env                        # Your credentials (gitignored)
├── src/
│   ├── main.py                 # FastAPI + endpoints
│   ├── config.py               # Settings
│   ├── db.py                   # Database
│   ├── models/                 # SQLAlchemy models
│   ├── discovery/              # YouTube API
│   ├── downloader/             # yt-dlp
│   ├── processor/              # Scene detect + FFmpeg
│   ├── metadata/               # LLM generation
│   ├── publisher/              # Instagram Graph API
│   ├── scheduler/              # APScheduler
│   └── cleanup/                # File/DB cleanup
├── scripts/
│   ├── deploy.sh               # VPS deployment
│   ├── setup_vps.sh            # VPS setup
│   ├── cli.py                  # Manual operations
│   └── entrypoint.sh           # Docker entrypoint
└── tests/                      # Unit + integration tests
```

## 11. Legal Warning ⚠️
**Reposting Oggy content carries copyright risk.** Xilam/GAUMONT actively enforces rights. Consider:
- Licensing content officially
- Creating transformative commentary
- Using public domain cartoons instead