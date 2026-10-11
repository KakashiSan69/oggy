from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.config import settings
from src.db import close_db, init_db
from src.scheduler import get_job_status, start_scheduler, stop_scheduler

# Configure structured logging
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer() if settings.app_env == "production"
        else structlog.dev.ConsoleRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logging.basicConfig(
    format="%(message)s",
    stream=sys.stdout,
    level=getattr(logging, settings.log_level),
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Oggy Reels Bot", env=settings.app_env)
    await init_db()
    start_scheduler()
    yield
    # Shutdown
    logger.info("Shutting down Oggy Reels Bot")
    stop_scheduler()
    await close_db()


app = FastAPI(
    title="Oggy Reels Bot",
    description="Automated Instagram Reels bot for Oggy cartoon content",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "oggy-reels-bot"}


@app.get("/jobs")
async def list_jobs():
    return {"jobs": get_job_status()}


@app.post("/jobs/{job_id}/trigger")
async def trigger_job(job_id: str):
    """Manually trigger a scheduled job."""
    from src.scheduler import scheduler

    job = scheduler.get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)

    job.modify(next_run_time=None)  # Run immediately
    return {"message": f"Job {job_id} triggered"}


@app.get("/stats")
async def get_stats():
    """Get system statistics."""
    from sqlalchemy import select, func
    from src.db import get_session
    from src.models import SourceVideo, Clip, Post, VideoStatus, ClipStatus, PostStatus

    async with get_session() as session:
        stats = {}

        # Source videos
        for status in VideoStatus:
            result = await session.execute(
                select(func.count(SourceVideo.id)).where(SourceVideo.status == status)
            )
            stats[f"source_videos_{status.value}"] = result.scalar()

        # Clips
        for status in ClipStatus:
            result = await session.execute(
                select(func.count(Clip.id)).where(Clip.status == status)
            )
            stats[f"clips_{status.value}"] = result.scalar()

        # Posts
        for status in PostStatus:
            result = await session.execute(
                select(func.count(Post.id)).where(Post.status == status)
            )
            stats[f"posts_{status.value}"] = result.scalar()

        # Today's posts
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        result = await session.execute(
            select(func.count(Post.id)).where(
                Post.status == PostStatus.PUBLISHED,
                Post.published_at >= today_start,
            )
        )
        stats["posts_published_today"] = result.scalar()

    return stats


@app.post("/discovery/run")
async def trigger_discovery():
    from src.discovery import run_discovery
    count = await run_discovery()
    return {"discovered": count}


@app.post("/download/run")
async def trigger_download():
    from src.downloader import download_pending_videos
    count = await download_pending_videos()
    return {"downloaded": count}


@app.post("/process/run")
async def trigger_process():
    from src.processor import process_pending_clips
    count = await process_pending_clips()
    return {"processed": count}


@app.post("/metadata/run")
async def trigger_metadata():
    from src.metadata import generate_metadata_for_clips
    count = await generate_metadata_for_clips()
    return {"generated": count}


@app.post("/publish/run")
async def trigger_publish():
    from src.publisher import publish_scheduled_posts
    count = await publish_scheduled_posts()
    return {"published": count}


@app.post("/cleanup/run")
async def trigger_cleanup():
    from src.cleanup import cleanup_old_files
    result = await cleanup_old_files()
    return result


def main():
    """Entry point for running as a script."""
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.app_env == "development",
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()