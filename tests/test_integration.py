from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from src.main import app
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test health check endpoint."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy", "service": "oggy-reels-bot"}


@pytest.mark.asyncio
async def test_stats_endpoint():
    """Test stats endpoint returns expected structure."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.get("/stats")
        assert response.status_code == 200
        
        data = response.json()
        expected_keys = {
            "source_videos_pending",
            "source_videos_downloading",
            "source_videos_downloaded",
            "source_videos_failed",
            "clips_pending",
            "clips_processing",
            "clips_ready",
            "clips_failed",
            "posts_draft",
            "posts_scheduled",
            "posts_publishing",
            "posts_published",
            "posts_failed",
            "posts_published_today",
        }
        assert expected_keys.issubset(data.keys())
        assert all(isinstance(v, int) for v in data.values())


@pytest.mark.asyncio
async def test_jobs_endpoint():
    """Test jobs endpoint returns scheduled jobs."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.get("/jobs")
        assert response.status_code == 200
        
        data = response.json()
        assert "jobs" in data
        assert isinstance(data["jobs"], list)
        assert len(data["jobs"]) == 6
        
        for job in data["jobs"]:
            assert "id" in job
            assert "name" in job
            assert "trigger" in job


@pytest.mark.asyncio
async def test_manual_trigger_endpoints():
    """Test manual trigger endpoints exist."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        # Test discovery trigger
        with patch('src.main.run_discovery', new_callable=AsyncMock) as mock:
            mock.return_value = 3
            response = await client.post("/discovery/run")
            assert response.status_code == 200
            assert response.json() == {"discovered": 3}

        # Test download trigger
        with patch('src.main.download_pending_videos', new_callable=AsyncMock) as mock:
            mock.return_value = 2
            response = await client.post("/download/run")
            assert response.status_code == 200
            assert response.json() == {"downloaded": 2}

        # Test process trigger
        with patch('src.main.process_pending_clips', new_callable=AsyncMock) as mock:
            mock.return_value = 4
            response = await client.post("/process/run")
            assert response.status_code == 200
            assert response.json() == {"processed": 4}

        # Test metadata trigger
        with patch('src.main.generate_metadata_for_clips', new_callable=AsyncMock) as mock:
            mock.return_value = 5
            response = await client.post("/metadata/run")
            assert response.status_code == 200
            assert response.json() == {"generated": 5}

        # Test publish trigger
        with patch('src.main.publish_scheduled_posts', new_callable=AsyncMock) as mock:
            mock.return_value = 1
            response = await client.post("/publish/run")
            assert response.status_code == 200
            assert response.json() == {"published": 1}

        # Test cleanup trigger
        with patch('src.main.cleanup_old_files', new_callable=AsyncMock) as mock:
            mock.return_value = {"files_removed": 10}
            response = await client.post("/cleanup/run")
            assert response.status_code == 200
            assert "files_removed" in response.json()


@pytest.mark.asyncio
async def test_job_trigger_endpoint():
    """Test manual job trigger."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        with patch('src.main.scheduler') as mock_scheduler:
            mock_job = MagicMock()
            mock_scheduler.get_job.return_value = mock_job
            
            response = await client.post("/jobs/discovery/trigger")
            assert response.status_code == 200
            assert "triggered" in response.json()["message"]
            
            # Test 404 for unknown job
            mock_scheduler.get_job.return_value = None
            response = await client.post("/jobs/unknown/trigger")
            assert response.status_code == 404