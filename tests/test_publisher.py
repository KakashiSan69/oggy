from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import Response

from src.publisher import StorageUploader, InstagramPublisher
from src.models import Clip, Post, PostStatus, SourceVideo


class TestStorageUploader:
    @pytest.fixture
    def uploader(self):
        with patch('boto3.client') as mock_boto:
            uploader = StorageUploader()
            uploader.s3 = MagicMock()
            return uploader

    @pytest.mark.asyncio
    async def test_upload_returns_public_url(self, uploader, tmp_path):
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"fake video content")

        uploader.s3.upload_file.return_value = None

        url = await uploader.upload(test_file, "clips/test.mp4")

        assert url == "https://pub-xxx.r2.dev/clips/test.mp4"
        uploader.s3.upload_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_clip(self, uploader):
        clip = Clip(
            id="00000000-0000-0000-0000-000000000001",
            source_video_id="00000000-0000-0000-0000-000000000002",
            clip_index=0,
            start_seconds=0,
            end_seconds=30,
            duration_seconds=30,
            status=ClipStatus.READY,
            local_path="/fake/clip.mp4",
        )
        clip.source_video = SourceVideo(
            id="00000000-0000-0000-0000-000000000002",
            youtube_id="test123",
            channel_id="UC123",
            title="Test",
        )

        uploader.s3.upload_file.return_value = None

        url = await uploader.upload_clip(clip)

        assert "test123" in url
        assert "clip.mp4" not in url  # Uses structured key


class TestInstagramPublisher:
    @pytest.fixture
    def publisher(self):
        return InstagramPublisher()

    @pytest.mark.asyncio
    async def test_create_media_container(self, publisher):
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_response = MagicMock(spec=Response)
            mock_response.json.return_value = {"id": "container_123"}
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            container_id = await publisher.create_media_container(
                "https://example.com/video.mp4",
                "Test caption",
            )

            assert container_id == "container_123"
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_wait_for_processing_success(self, publisher):
        with patch('httpx.AsyncClient.get') as mock_get:
            # First call: IN_PROGRESS, Second: FINISHED
            responses = [
                MagicMock(json=lambda: {"status_code": "IN_PROGRESS"}),
                MagicMock(json=lambda: {"status_code": "FINISHED"}),
            ]
            for r in responses:
                r.raise_for_status = MagicMock()
            mock_get.side_effect = responses

            with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                result = await publisher.wait_for_processing("container_123", max_wait=10)
                assert result is True
                assert mock_get.call_count == 2

    @pytest.mark.asyncio
    async def test_wait_for_processing_error(self, publisher):
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"status_code": "ERROR"}
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            with patch('asyncio.sleep', new_callable=AsyncMock):
                result = await publisher.wait_for_processing("container_123")
                assert result is False

    @pytest.mark.asyncio
    async def test_publish_container(self, publisher):
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_response = MagicMock(spec=Response)
            mock_response.json.return_value = {"id": "media_123"}
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            media_id = await publisher.publish_container("container_123")
            assert media_id == "media_123"

    @pytest.mark.asyncio
    async def test_get_media_permalink(self, publisher):
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = MagicMock(spec=Response)
            mock_response.json.return_value = {"permalink": "https://instagram.com/reel/abc"}
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            permalink = await publisher.get_media_permalink("media_123")
            assert permalink == "https://instagram.com/reel/abc"


class TestPublishScheduledPosts:
    @pytest.mark.asyncio
    async def test_respects_daily_limit(self, async_session):
        from src.publisher import publish_scheduled_posts
        from src.config import settings

        # Create posts published today
        for i in range(settings.max_posts_per_day):
            post = Post(
                clip_id="00000000-0000-0000-0000-000000000001",
                status=PostStatus.PUBLISHED,
                published_at=datetime.now(timezone.utc),
            )
            async_session.add(post)
        await async_session.commit()

        # Should return 0 without publishing more
        count = await publish_scheduled_posts()
        assert count == 0