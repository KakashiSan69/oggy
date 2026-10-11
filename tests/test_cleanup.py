from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.cleanup import cleanup_old_files, _cleanup_orphaned_files
from src.models import SourceVideo, Clip, ClipStatus, Post, PostStatus, VideoStatus


class TestCleanup:
    @pytest.mark.asyncio
    async def test_cleanup_old_source_videos(self, async_session, tmp_path):
        from src.config import settings
        from src.cleanup import _cleanup_source_videos

        # Create old downloaded video
        old_date = datetime.now(timezone.utc) - timedelta(days=settings.keep_source_videos_days + 1)
        video = SourceVideo(
            youtube_id="old123",
            channel_id="UC123",
            title="Old Video",
            status=VideoStatus.DOWNLOADED,
            local_path=str(tmp_path / "old.mp4"),
            downloaded_at=old_date,
        )
        async_session.add(video)
        await async_session.commit()

        # Create the file
        (tmp_path / "old.mp4").write_bytes(b"fake")

        with patch('src.cleanup.settings.data_dir', tmp_path):
            deleted = await _cleanup_source_videos()

        assert deleted == 1
        assert not (tmp_path / "old.mp4").exists()

        # Verify deleted from DB
        result = await async_session.get(SourceVideo, video.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_cleanup_keeps_recent_videos(self, async_session, tmp_path):
        from src.config import settings
        from src.cleanup import _cleanup_source_videos

        recent_date = datetime.now(timezone.utc) - timedelta(days=1)
        video = SourceVideo(
            youtube_id="recent123",
            channel_id="UC123",
            title="Recent Video",
            status=VideoStatus.DOWNLOADED,
            local_path=str(tmp_path / "recent.mp4"),
            downloaded_at=recent_date,
        )
        async_session.add(video)
        await async_session.commit()

        (tmp_path / "recent.mp4").write_bytes(b"fake")

        with patch('src.cleanup.settings.data_dir', tmp_path):
            deleted = await _cleanup_source_videos()

        assert deleted == 0
        assert (tmp_path / "recent.mp4").exists()

    @pytest.mark.asyncio
    async def test_cleanup_old_clips(self, async_session, tmp_path):
        from src.config import settings
        from src.cleanup import _cleanup_clips

        old_date = datetime.now(timezone.utc) - timedelta(days=settings.keep_clips_days + 1)
        source = SourceVideo(
            id="00000000-0000-0000-0000-000000000001",
            youtube_id="src123",
            channel_id="UC123",
            title="Source",
        )
        async_session.add(source)
        await async_session.commit()

        clip = Clip(
            source_video_id=source.id,
            clip_index=0,
            start_seconds=0,
            end_seconds=30,
            duration_seconds=30,
            status=ClipStatus.READY,
            local_path=str(tmp_path / "clip.mp4"),
            created_at=old_date,
        )
        async_session.add(clip)
        await async_session.commit()

        (tmp_path / "clip.mp4").write_bytes(b"fake")
        (tmp_path / "clip_reels.mp4").write_bytes(b"fake reels")

        with patch('src.cleanup.settings.data_dir', tmp_path):
            deleted = await _cleanup_clips()

        assert deleted == 1
        assert not (tmp_path / "clip.mp4").exists()
        assert not (tmp_path / "clip_reels.mp4").exists()

    @pytest.mark.asyncio
    async def test_cleanup_orphaned_files(self, async_session, tmp_path):
        from src.config import settings

        # Create referenced file
        video = SourceVideo(
            youtube_id="ref123",
            channel_id="UC123",
            title="Referenced",
            status=VideoStatus.DOWNLOADED,
            local_path=str(tmp_path / "referenced.mp4"),
        )
        async_session.add(video)
        await async_session.commit()

        (tmp_path / "referenced.mp4").write_bytes(b"referenced")
        (tmp_path / "orphaned.mp4").write_bytes(b"orphaned")

        with patch('src.cleanup.settings.data_dir', tmp_path):
            files_removed, bytes_freed = await _cleanup_orphaned_files()

        assert files_removed == 1
        assert bytes_freed > 0
        assert (tmp_path / "referenced.mp4").exists()
        assert not (tmp_path / "orphaned.mp4").exists()