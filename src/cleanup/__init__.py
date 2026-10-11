from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.config import settings
from src.db import get_session
from src.models import Clip, ClipStatus, Post, PostStatus, SourceVideo, VideoStatus

logger = logging.getLogger(__name__)


async def cleanup_old_files() -> dict:
    """Clean up old files and database records."""
    results = {
        "source_videos_deleted": 0,
        "clips_deleted": 0,
        "posts_deleted": 0,
        "files_removed": 0,
        "bytes_freed": 0,
    }

    # Clean up old source videos
    results["source_videos_deleted"] += await _cleanup_source_videos()
    results["clips_deleted"] += await _cleanup_clips()
    results["posts_deleted"] += await _cleanup_posts()
    results["files_removed"], results["bytes_freed"] = await _cleanup_orphaned_files()

    logger.info(f"Cleanup completed: {results}")
    return results


async def _cleanup_source_videos() -> int:
    """Delete old downloaded source videos."""
    from sqlalchemy import select, delete

    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.keep_source_videos_days)

    async with get_session() as session:
        # Find old downloaded videos
        result = await session.execute(
            select(SourceVideo).where(
                SourceVideo.status == VideoStatus.DOWNLOADED,
                SourceVideo.downloaded_at < cutoff,
            )
        )
        videos = result.scalars().all()

        deleted = 0
        for video in videos:
            # Delete local file
            if video.local_path:
                path = Path(video.local_path)
                if path.exists():
                    path.unlink()

            # Delete from DB (cascades to clips)
            await session.delete(video)
            deleted += 1

        await session.commit()
        return deleted


async def _cleanup_clips() -> int:
    """Delete old processed clips."""
    from sqlalchemy import select, delete

    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.keep_clips_days)

    async with get_session() as session:
        result = await session.execute(
            select(Clip).where(
                Clip.status.in_([ClipStatus.READY, ClipStatus.FAILED]),
                Clip.created_at < cutoff,
            )
        )
        clips = result.scalars().all()

        deleted = 0
        for clip in clips:
            # Delete local file
            if clip.local_path:
                path = Path(clip.local_path)
                if path.exists():
                    path.unlink()

            # Also delete reels version
            reels_path = path.with_name(f"{path.stem}_reels.mp4")
            if reels_path.exists():
                reels_path.unlink()

            await session.delete(clip)
            deleted += 1

        await session.commit()
        return deleted


async def _cleanup_posts() -> int:
    """Delete old failed posts."""
    from sqlalchemy import select

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    async with get_session() as session:
        result = await session.execute(
            select(Post).where(
                Post.status == PostStatus.FAILED,
                Post.created_at < cutoff,
            )
        )
        posts = result.scalars().all()

        deleted = 0
        for post in posts:
            await session.delete(post)
            deleted += 1

        await session.commit()
        return deleted


async def _cleanup_orphaned_files() -> tuple[int, int]:
    """Remove files in data directories that aren't referenced in DB."""
    from sqlalchemy import select

    data_dirs = [
        settings.data_dir / "source_videos",
        settings.data_dir / "clips",
    ]

    # Get all referenced paths
    referenced = set()

    async with get_session() as session:
        result = await session.execute(select(SourceVideo.local_path))
        for row in result:
            if row[0]:
                referenced.add(Path(row[0]).resolve())

        result = await session.execute(select(Clip.local_path))
        for row in result:
            if row[0]:
                referenced.add(Path(row[0]).resolve())
                # Also reels version
                p = Path(row[0])
                referenced.add(p.with_name(f"{p.stem}_reels.mp4").resolve())

    files_removed = 0
    bytes_freed = 0

    for data_dir in data_dirs:
        if not data_dir.exists():
            continue

        for file_path in data_dir.rglob("*"):
            if file_path.is_file():
                resolved = file_path.resolve()
                if resolved not in referenced:
                    try:
                        size = file_path.stat().st_size
                        file_path.unlink()
                        files_removed += 1
                        bytes_freed += size
                    except Exception as e:
                        logger.warning(f"Failed to remove orphaned file {file_path}: {e}")

    return files_removed, bytes_freed