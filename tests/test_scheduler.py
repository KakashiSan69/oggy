from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from src.scheduler import (
    setup_scheduler,
    start_scheduler,
    stop_scheduler,
    get_job_status,
    run_discovery_job,
    run_download_job,
    run_processing_job,
    run_metadata_job,
    run_publishing_job,
    run_cleanup_job,
)


class TestScheduler:
    @pytest.fixture
    def scheduler(self):
        sched = setup_scheduler()
        yield sched
        stop_scheduler()

    def test_scheduler_has_all_jobs(self, scheduler):
        jobs = scheduler.get_jobs()
        job_ids = {job.id for job in jobs}
        
        expected = {
            "discovery",
            "download",
            "processing",
            "metadata",
            "publishing",
            "cleanup",
        }
        assert expected.issubset(job_ids)

    def test_job_status_format(self, scheduler):
        status = get_job_status()
        assert isinstance(status, list)
        assert len(status) == 6
        
        for job in status:
            assert "id" in job
            assert "name" in job
            assert "next_run" in job
            assert "trigger" in job

    @pytest.mark.asyncio
    async def test_run_discovery_job(self):
        with patch('src.scheduler.run_discovery', new_callable=AsyncMock) as mock:
            mock.return_value = 5
            result = await run_discovery_job()
            assert "Discovered 5 new videos" in result

    @pytest.mark.asyncio
    async def test_run_download_job(self):
        with patch('src.scheduler.download_pending_videos', new_callable=AsyncMock) as mock:
            mock.return_value = 3
            result = await run_download_job()
            assert "Downloaded 3 videos" in result

    @pytest.mark.asyncio
    async def test_run_processing_job(self):
        with patch('src.scheduler.process_pending_clips', new_callable=AsyncMock) as mock:
            mock.return_value = 2
            result = await run_processing_job()
            assert "Created 2 clips" in result

    @pytest.mark.asyncio
    async def test_run_metadata_job(self):
        with patch('src.scheduler.generate_metadata_for_clips', new_callable=AsyncMock) as mock:
            mock.return_value = 4
            result = await run_metadata_job()
            assert "Generated metadata for 4 clips" in result

    @pytest.mark.asyncio
    async def test_run_publishing_job(self):
        with patch('src.scheduler.publish_scheduled_posts', new_callable=AsyncMock) as mock:
            mock.return_value = 1
            result = await run_publishing_job()
            assert "Published 1 posts" in result

    @pytest.mark.asyncio
    async def test_run_cleanup_job(self):
        with patch('src.scheduler.cleanup_old_files', new_callable=AsyncMock) as mock:
            mock.return_value = {"source_videos_deleted": 2, "clips_deleted": 5}
            result = await run_cleanup_job()
            assert "Cleaned up" in result