from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import yt_dlp

from src.config import settings
from src.db import get_session
from src.models import SourceVideo, VideoStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class VideoDownloader:
    def __init__(self, download_dir: Path | None = None):
        self.download_dir = download_dir or settings.data_dir / "source_videos"
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def _get_ydl_opts(self, output_path: Path) -> dict:
        return {
            "format": "bv*[height<=1080]+ba/b[height<=1080]",
            "merge_output_format": "mp4",
            "outtmpl": str(output_path),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": False,
            "extract_flat": False,
            "writesubtitles": False,
            "writeautomaticsub": False,
            "postprocessors": [{
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }],
        }

    async def download(self, source_video: SourceVideo) -> Path | None:
        url = f"https://www.youtube.com/watch?v={source_video.youtube_id}"
        output_path = self.download_dir / f"{source_video.youtube_id}.%(ext)s"

        ydl_opts = self._get_ydl_opts(output_path)

        try:
            loop = asyncio.get_event_loop()
            final_path = await loop.run_in_executor(None, self._download_sync, url, ydl_opts)
            return final_path
        except Exception as e:
            logger.error(f"Download failed for {source_video.youtube_id}: {e}")
            raise

    def _download_sync(self, url: str, ydl_opts: dict) -> Path:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filepath = ydl.prepare_filename(info)
            return Path(filepath).with_suffix(".mp4")


async def download_pending_videos(limit: int = 10) -> int:
    """Download pending source videos."""
    async with get_session() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(SourceVideo)
            .where(SourceVideo.status == VideoStatus.PENDING)
            .order_by(SourceVideo.discovered_at)
            .limit(limit)
        )
        videos = result.scalars().all()

    if not videos:
        logger.info("No pending videos to download")
        return 0

    downloader = VideoDownloader()
    downloaded = 0

    for video in videos:
        async with get_session() as session:
            video = await session.merge(video)
            video.status = VideoStatus.DOWNLOADING
            await session.commit()

        try:
            file_path = await downloader.download(video)

            async with get_session() as session:
                video = await session.merge(video)
                video.status = VideoStatus.DOWNLOADED
                video.local_path = str(file_path)
                video.file_size_bytes = file_path.stat().st_size
                video.downloaded_at = datetime.now(timezone.utc)
                await session.commit()

            downloaded += 1
            logger.info(f"Downloaded: {video.youtube_id} -> {file_path}")

        except Exception as e:
            async with get_session() as session:
                video = await session.merge(video)
                video.status = VideoStatus.FAILED
                video.error_message = str(e)
                await session.commit()
            logger.error(f"Failed to download {video.youtube_id}: {e}")

    return downloaded