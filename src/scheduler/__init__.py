from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import settings

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=settings.timezone)


def setup_scheduler() -> AsyncIOScheduler:
    """Configure and return the scheduler with all jobs."""

    # Discovery job
    scheduler.add_job(
        run_discovery_job,
        CronTrigger.from_crontab(settings.discovery_schedule),
        id="discovery",
        name="Discover new YouTube videos",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

    # Download job
    scheduler.add_job(
        run_download_job,
        CronTrigger.from_crontab("*/15 * * * *"),  # Every 15 minutes
        id="download",
        name="Download pending videos",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

    # Processing job
    scheduler.add_job(
        run_processing_job,
        CronTrigger.from_crontab("*/10 * * * *"),  # Every 10 minutes
        id="processing",
        name="Process videos into clips",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

    # Metadata generation job
    scheduler.add_job(
        run_metadata_job,
        CronTrigger.from_crontab("*/10 * * * *"),  # Every 10 minutes
        id="metadata",
        name="Generate AI metadata for clips",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

    # Publishing job
    scheduler.add_job(
        run_publishing_job,
        CronTrigger.from_crontab(settings.posting_schedule),
        id="publishing",
        name="Publish scheduled posts to Instagram",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

    # Cleanup job
    scheduler.add_job(
        run_cleanup_job,
        CronTrigger.from_crontab(settings.cleanup_schedule),
        id="cleanup",
        name="Clean up old files and database records",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

    return scheduler


# Job wrappers with error handling
async def run_job_wrapper(job_name: str, job_func: Callable) -> None:
    """Wrapper to run job with logging and error handling."""
    logger.info(f"Starting job: {job_name}")
    start = datetime.now(timezone.utc)
    try:
        result = await job_func()
        duration = (datetime.now(timezone.utc) - start).total_seconds()
        logger.info(f"Job {job_name} completed in {duration:.1f}s: {result}")
    except Exception as e:
        duration = (datetime.now(timezone.utc) - start).total_seconds()
        logger.exception(f"Job {job_name} failed after {duration:.1f}s: {e}")


async def run_discovery_job() -> str:
    from src.discovery import run_discovery
    count = await run_discovery()
    return f"Discovered {count} new videos"


async def run_download_job() -> str:
    from src.downloader import download_pending_videos
    count = await download_pending_videos()
    return f"Downloaded {count} videos"


async def run_processing_job() -> str:
    from src.processor import process_pending_clips
    count = await process_pending_clips()
    return f"Created {count} clips"


async def run_metadata_job() -> str:
    from src.metadata import generate_metadata_for_clips
    count = await generate_metadata_for_clips()
    return f"Generated metadata for {count} clips"


async def run_publishing_job() -> str:
    from src.publisher import publish_scheduled_posts
    count = await publish_scheduled_posts()
    return f"Published {count} posts"


async def run_cleanup_job() -> str:
    from src.cleanup import cleanup_old_files
    result = await cleanup_old_files()
    return f"Cleaned up: {result}"


def start_scheduler() -> None:
    """Start the scheduler."""
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")


def stop_scheduler() -> None:
    """Stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("Scheduler stopped")


def get_job_status() -> list[dict]:
    """Get status of all scheduled jobs."""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        })
    return jobs