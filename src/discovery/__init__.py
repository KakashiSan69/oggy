from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.config import settings
from src.db import get_session
from src.models import SourceVideo, VideoStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class YouTubeDiscovery:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.youtube_api_key
        self.youtube = build("youtube", "v3", developerKey=self.api_key)

    async def discover_new_videos(self, max_results: int = 50) -> list[dict]:
        all_videos = []
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=settings.max_source_video_age_days)

        for channel_id in settings.youtube_channels:
            try:
                videos = await self._fetch_channel_videos(channel_id, max_results, cutoff_date)
                all_videos.extend(videos)
            except Exception as e:
                logger.error(f"Failed to fetch videos for channel {channel_id}: {e}")

        return all_videos

    async def _fetch_channel_videos(
        self, channel_id: str, max_results: int, cutoff_date: datetime
    ) -> list[dict]:
        videos = []
        next_page_token = None

        while len(videos) < max_results:
            request = self.youtube.search().list(
                part="snippet",
                channelId=channel_id,
                type="video",
                order="date",
                maxResults=min(50, max_results - len(videos)),
                pageToken=next_page_token,
                publishedAfter=cutoff_date.isoformat().replace("+00:00", "Z"),
            )
            response = request.execute()

            for item in response.get("items", []):
                video_id = item["id"]["videoId"]
                snippet = item["snippet"]
                published_at = datetime.fromisoformat(snippet["publishedAt"].replace("Z", "+00:00"))

                videos.append({
                    "youtube_id": video_id,
                    "channel_id": channel_id,
                    "title": snippet["title"],
                    "description": snippet.get("description", ""),
                    "published_at": published_at,
                    "thumbnail_url": snippet["thumbnails"].get("high", {}).get("url"),
                })

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

        return videos

    async def get_video_details(self, video_ids: list[str]) -> dict[str, dict]:
        if not video_ids:
            return {}

        details = {}
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i:i + 50]
            request = self.youtube.videos().list(
                part="contentDetails,statistics",
                id=",".join(batch),
            )
            response = request.execute()

            for item in response.get("items", []):
                vid = item["id"]
                duration = item["contentDetails"]["duration"]
                details[vid] = {
                    "duration_seconds": self._parse_duration(duration),
                    "view_count": int(item["statistics"].get("viewCount", 0)),
                    "like_count": int(item["statistics"].get("likeCount", 0)),
                }

        return details

    @staticmethod
    def _parse_duration(iso_duration: str) -> int:
        import re
        pattern = r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"
        match = re.match(pattern, iso_duration)
        if not match:
            return 0
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        return hours * 3600 + minutes * 60 + seconds


class RSSDiscovery:
    """Fallback discovery using YouTube RSS feeds."""

    def __init__(self):
        self.base_url = "https://www.youtube.com/feeds/videos.xml"

    async def discover_new_videos(self, max_results: int = 50) -> list[dict]:
        import httpx
        import feedparser

        all_videos = []
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=settings.max_source_video_age_days)

        async with httpx.AsyncClient(timeout=30.0) as client:
            for channel_id in settings.youtube_channels:
                try:
                    url = f"{self.base_url}?channel_id={channel_id}"
                    response = await client.get(url)
                    response.raise_for_status()

                    feed = feedparser.parse(response.text)
                    for entry in feed.entries[:max_results]:
                        published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                        if published < cutoff_date:
                            continue

                        video_id = entry.get("yt_videoid") or entry.id.split(":")[-1]
                        all_videos.append({
                            "youtube_id": video_id,
                            "channel_id": channel_id,
                            "title": entry.title,
                            "description": entry.get("summary", ""),
                            "published_at": published,
                            "thumbnail_url": entry.get("media_thumbnail", [{}])[0].get("url"),
                        })
                except Exception as e:
                    logger.error(f"RSS discovery failed for {channel_id}: {e}")

        return all_videos


async def save_discovered_videos(videos: list[dict]) -> int:
    """Save discovered videos to database, return count of new videos."""
    async with get_session() as session:
        new_count = 0
        for video in videos:
            existing = await session.get(SourceVideo, video["youtube_id"])
            if existing:
                continue

            source_video = SourceVideo(
                youtube_id=video["youtube_id"],
                channel_id=video["channel_id"],
                title=video["title"],
                description=video["description"],
                published_at=video["published_at"],
                thumbnail_url=video["thumbnail_url"],
                status=VideoStatus.PENDING,
            )
            session.add(source_video)
            new_count += 1

        await session.commit()
        logger.info(f"Discovered {new_count} new videos")
        return new_count


async def run_discovery() -> int:
    """Main discovery job entry point."""
    logger.info("Starting video discovery...")

    # Try YouTube API first
    discovery = YouTubeDiscovery()
    try:
        videos = await discovery.discover_new_videos()
        if videos:
            return await save_discovered_videos(videos)
    except HttpError as e:
        if e.resp.status in (403, 429):
            logger.warning(f"YouTube API quota exceeded or forbidden: {e}, falling back to RSS")
        else:
            raise

    # Fallback to RSS
    logger.info("Falling back to RSS discovery...")
    rss = RSSDiscovery()
    videos = await rss.discover_new_videos()
    return await save_discovered_videos(videos)