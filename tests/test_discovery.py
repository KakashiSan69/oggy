from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from src.discovery import YouTubeDiscovery, RSSDiscovery, save_discovered_videos, run_discovery
from src.models import SourceVideo, VideoStatus


class TestYouTubeDiscovery:
    @pytest.fixture
    def discovery(self):
        return YouTubeDiscovery(api_key="test_key")

    @pytest.mark.asyncio
    async def test_parse_duration(self):
        assert YouTubeDiscovery._parse_duration("PT1H30M15S") == 5415
        assert YouTubeDiscovery._parse_duration("PT15M") == 900
        assert YouTubeDiscovery._parse_duration("PT30S") == 30
        assert YouTubeDiscovery._parse_duration("PT2H") == 7200
        assert YouTubeDiscovery._parse_duration("PT1H30M") == 5400
        assert YouTubeDiscovery._parse_duration("invalid") == 0

    @pytest.mark.asyncio
    async def test_discover_new_videos_empty_channels(self, discovery):
        discovery.youtube_channels = []
        videos = await discovery.discover_new_videos()
        assert videos == []


class TestRSSDiscovery:
    @pytest.fixture
    def rss_discovery(self):
        return RSSDiscovery()

    @pytest.mark.asyncio
    async def test_discover_new_videos_empty_channels(self, rss_discovery):
        from src.config import settings
        settings.youtube_channel_ids = ""
        videos = await rss_discovery.discover_new_videos()
        assert videos == []


class TestSaveDiscoveredVideos:
    @pytest.mark.asyncio
    async def test_save_new_videos(self, async_session):
        videos = [
            {
                "youtube_id": "abc123",
                "channel_id": "UC123",
                "title": "Test Video",
                "description": "Test desc",
                "published_at": datetime.now(timezone.utc),
                "thumbnail_url": "https://example.com/thumb.jpg",
            }
        ]
        count = await save_discovered_videos(videos)
        assert count == 1

        # Verify in DB
        result = await async_session.execute(
            SourceVideo.__table__.select().where(SourceVideo.youtube_id == "abc123")
        )
        row = result.first()
        assert row is not None
        assert row.title == "Test Video"
        assert row.status == VideoStatus.PENDING

    @pytest.mark.asyncio
    async def test_skip_existing_videos(self, async_session):
        # Add existing video
        existing = SourceVideo(
            youtube_id="abc123",
            channel_id="UC123",
            title="Existing",
            status=VideoStatus.PENDING,
        )
        async_session.add(existing)
        await async_session.commit()

        videos = [
            {
                "youtube_id": "abc123",
                "channel_id": "UC123",
                "title": "Test Video",
                "description": "Test desc",
                "published_at": datetime.now(timezone.utc),
                "thumbnail_url": "https://example.com/thumb.jpg",
            }
        ]
        count = await save_discovered_videos(videos)
        assert count == 0  # Should not add duplicate