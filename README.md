# Oggy Reels Bot

Automated Instagram Reels bot that discovers Oggy cartoon videos on YouTube, downloads them, extracts interesting clips, generates AI-powered metadata, and publishes to Instagram on a schedule.

## Architecture

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│  Discovery  │───▶│  Download    │───▶│  Processing │───▶│  Metadata    │───▶│  Publishing │
│  (YouTube)  │    │  (yt-dlp)    │    │  (FFmpeg)   │    │  (LLM)       │    │  (IG API)   │
└─────────────┘    └──────────────┘    └─────────────┘    └──────────────┘    └─────────────┘
       │                  │                   │                  │                  │
       ▼                  ▼                   ▼                  ▼                  ▼
  YouTube API       yt-dlp              Scene detect +      GPT-4o-mini      Graph API
  / RSS fallback    1080p MP4           MoviePy 9:16        hashtags         + R2 storage
```

## Features

- **Discovery**: YouTube Data API v3 with RSS fallback
- **Download**: yt-dlp for reliable 1080p MP4 downloads
- **Smart Clipping**: Scene detection + motion/color scoring for best moments
- **Reels Format**: Auto-resize to 9:16 (1080x1920), add watermark
- **AI Metadata**: GPT-4o-mini / Claude / Ollama for captions, hashtags, alt text
- **Publishing**: Instagram Graph API (official) with Cloudflare R2 storage
- **Scheduling**: APScheduler with cron expressions
- **Monitoring**: Health endpoint, job status, stats API
- **Cleanup**: Automatic removal of old files and database records

## Prerequisites

- VPS with Docker & Docker Compose (2 vCPU, 4GB RAM, 50GB SSD)
- Domain name with DNS pointing to VPS
- YouTube Data API v3 key
- Instagram Business/Creator account + Facebook Page
- Meta Developer App with Instagram Graph API permissions
- Cloudflare R2 (or AWS S3) bucket for video storage
- OpenAI API key (or Anthropic/Ollama)

## Quick Start

### 1. Clone and Configure

```bash
git clone <your-repo>
cd oggy-reels-bot
cp .env.example .env
# Edit .env with all your credentials
```

### 2. Required Environment Variables

| Variable | Description |
|----------|-------------|
| `YOUTUBE_API_KEY` | YouTube Data API v3 key |
| `YOUTUBE_CHANNEL_IDS` | Comma-separated channel IDs to monitor |
| `IG_APP_ID` | Meta App ID |
| `IG_APP_SECRET` | Meta App Secret |
| `IG_ACCESS_TOKEN` | Long-lived Instagram access token |
| `IG_USER_ID` | Instagram Business Account ID |
| `IG_PAGE_ID` | Facebook Page ID |
| `LLM_API_KEY` | OpenAI/Anthropic API key |
| `STORAGE_ENDPOINT` | R2/S3 endpoint URL |
| `STORAGE_ACCESS_KEY` | R2/S3 access key |
| `STORAGE_SECRET_KEY` | R2/S3 secret key |
| `STORAGE_BUCKET` | Bucket name |
| `STORAGE_PUBLIC_URL` | Public CDN URL (e.g., `https://pub-xxx.r2.dev`) |

### 3. Get Instagram Access Token

```bash
# 1. Get short-lived token from Meta Graph Explorer
# 2. Exchange for long-lived token:
curl -X GET "https://graph.facebook.com/v20.0/oauth/access_token?grant_type=fb_exchange_token&client_id={APP_ID}&client_secret={APP_SECRET}&fb_exchange_token={SHORT_TOKEN}"

# 3. Store in .env as IG_ACCESS_TOKEN
```

### 4. Deploy with Docker Compose

```bash
# Build and start
docker compose up -d --build

# View logs
docker compose logs -f app

# Check health
curl https://your-domain.com/health
```

### 5. SSL Certificate (Let's Encrypt)

```bash
# First run (replace your-domain.com):
docker compose run --rm certbot certonly --webroot -w /var/www/certbot -d your-domain.com

# Certificates auto-renew via certbot container
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/stats` | GET | System statistics |
| `/jobs` | GET | List scheduled jobs |
| `/jobs/{id}/trigger` | POST | Manually trigger a job |
| `/discovery/run` | POST | Run discovery manually |
| `/download/run` | POST | Run download manually |
| `/process/run` | POST | Run processing manually |
| `/metadata/run` | POST | Run metadata generation |
| `/publish/run` | POST | Run publishing manually |
| `/cleanup/run` | POST | Run cleanup manually |

## Scheduling

Default schedules (UTC, configurable in `.env`):

| Job | Schedule | Description |
|-----|----------|-------------|
| Discovery | `0 */6 * * *` | Every 6 hours |
| Download | `*/15 * * * *` | Every 15 minutes |
| Processing | `*/10 * * * *` | Every 10 minutes |
| Metadata | `*/10 * * * *` | Every 10 minutes |
| Publishing | `0 9,14,19 * * *` | 9AM, 2PM, 7PM |
| Cleanup | `0 3 * * *` | Daily at 3AM |

## Database Schema

- **source_videos**: Discovered YouTube videos
- **clips**: Extracted clips with metadata
- **posts**: Instagram publications

## Monitoring

```bash
# View job status
curl https://your-domain.com/jobs

# View stats
curl https://your-domain.com/stats

# Follow logs
docker compose logs -f app | jq .
```

## Manual Operations

```bash
# Run discovery now
curl -X POST https://your-domain.com/discovery/run

# Publish pending posts
curl -X POST https://your-domain.com/publish/run

# Check database
docker compose exec postgres psql -U oggy -d oggy_bot
```

## Legal Warning ⚠️

**Important**: Reposting cartoon content carries significant risk:

- **YouTube ToS**: Downloading videos violates ToS unless explicitly permitted
- **Instagram ToS**: Reposting non-original content triggers "unoriginal content" demotion
- **Copyright**: Oggy is owned by Xilam/GAUMONT - they actively enforce rights
- **Monetization**: You likely cannot monetize this content

**Safer alternatives**:
1. License content from Xilam or authorized distributors
2. Create transformative commentary/curation
3. Focus on public domain / Creative Commons cartoons
4. Build a fan community with discussion, trivia, fan art

## Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/
ruff format src/

# Type check
mypy src/
```

## Project Structure

```
oggy-reels-bot/
├── docker-compose.yml
├── Dockerfile
├── nginx.conf
├── pyproject.toml
├── .env.example
├── src/
│   ├── main.py              # FastAPI app + endpoints
│   ├── config.py            # Pydantic settings
│   ├── db.py                # Database connection
│   ├── models/              # SQLAlchemy models
│   ├── discovery/           # YouTube API + RSS
│   ├── downloader/          # yt-dlp wrapper
│   ├── processor/           # Scene detect + FFmpeg + MoviePy
│   ├── metadata/            # LLM metadata generation
│   ├── publisher/           # Instagram Graph API + R2 upload
│   ├── scheduler/           # APScheduler jobs
│   └── cleanup/             # File/DB cleanup
├── scripts/
└── tests/
```

## Troubleshooting

### "Video processing failed" on Instagram
- Ensure video is publicly accessible via HTTPS
- Check video codec: H.264 High Profile, AAC audio
- Max 100MB, 90 seconds for Reels

### "Quota exceeded" on YouTube API
- Reduce `DISCOVERY_SCHEDULE` frequency
- Use RSS fallback more aggressively
- Request quota increase from Google

### Posts not publishing
- Check `IG_ACCESS_TOKEN` hasn't expired (60 days)
- Verify Instagram account is Business/Creator
- Check `MAX_POSTS_PER_DAY` limit

### High memory usage
- Reduce `CLIPS_PER_SOURCE`
- Lower `VIDEO_CRF` (higher = smaller)
- Process fewer videos in parallel

## License

MIT - See LICENSE file