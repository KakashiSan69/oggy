from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.processor import SceneDetector, ClipScorer, VideoClipper
from src.metadata import MetadataGenerator
from src.models import Clip, ClipStatus, SourceVideo


class TestSceneDetector:
    def test_detect_scenes_returns_list(self):
        """Test that detect_scenes returns list of tuples."""
        # This would need a real video file - mock for unit test
        with patch('src.processor.detect') as mock_detect:
            mock_detect.return_value = [
                (MagicMock(get_seconds=lambda: 0.0), MagicMock(get_seconds=lambda: 10.0)),
                (MagicMock(get_seconds=lambda: 10.0), MagicMock(get_seconds=lambda: 25.0)),
            ]
            scenes = SceneDetector.detect_scenes(Path("/fake/video.mp4"))
            assert scenes == [(0.0, 10.0), (10.0, 25.0)]


class TestClipScorer:
    @pytest.mark.asyncio
    async def test_score_segment_returns_float(self):
        """Test score_segment returns a float between 0 and 1."""
        with patch('cv2.VideoCapture') as mock_cap:
            mock_cap_instance = MagicMock()
            mock_cap.return_value = mock_cap_instance
            mock_cap_instance.get.side_effect = lambda x: 30 if x == 5 else 900  # fps, frame_count
            mock_cap_instance.read.side_effect = [
                (True, MagicMock()) for _ in range(10)
            ] + [(False, None)]
            
            score = ClipScorer.score_segment(Path("/fake/video.mp4"), 0, 5)
            assert isinstance(score, float)
            assert 0 <= score <= 1


class TestVideoClipper:
    @pytest.fixture
    def clipper(self, tmp_path):
        return VideoClipper(output_dir=tmp_path / "clips")

    @pytest.fixture
    def source_video(self):
        return SourceVideo(
            id="00000000-0000-0000-0000-000000000001",
            youtube_id="test123",
            channel_id="UC123",
            title="Test Video",
            status=VideoStatus.DOWNLOADED,
            local_path="/fake/video.mp4",
            downloaded_at=datetime.now(timezone.utc),
        )

    @pytest.mark.asyncio
    async def test_find_best_clips_returns_tuples(self, clipper):
        with patch.object(clipper, '_get_duration', return_value=120):
            with patch.object(SceneDetector, 'detect_scenes', return_value=[(0, 30), (30, 60), (60, 90)]):
                with patch.object(ClipScorer, 'score_segment', return_value=0.8):
                    clips = clipper.find_best_clips(
                        Path("/fake/video.mp4"),
                        num_clips=2,
                        min_duration=15,
                        max_duration=60,
                    )
                    assert len(clips) == 2
                    assert all(len(c) == 3 for c in clips)  # (start, end, score)

    @pytest.mark.asyncio
    async def test_find_best_clips_filters_short_segments(self, clipper):
        with patch.object(clipper, '_get_duration', return_value=120):
            with patch.object(SceneDetector, 'detect_scenes', return_value=[(0, 5), (5, 30)]):  # First too short
                with patch.object(ClipScorer, 'score_segment', return_value=0.8):
                    clips = clipper.find_best_clips(
                        Path("/fake/video.mp4"),
                        num_clips=2,
                        min_duration=15,
                        max_duration=60,
                    )
                    assert len(clips) == 1  # Only one valid clip
                    assert clips[0][0] == 5


class TestMetadataGenerator:
    @pytest.fixture
    def generator(self):
        return MetadataGenerator()

    @pytest.mark.asyncio
    async def test_fallback_metadata(self, generator):
        clip = Clip(
            id="00000000-0000-0000-0000-000000000002",
            source_video_id="00000000-0000-0000-0000-000000000001",
            clip_index=0,
            start_seconds=0,
            end_seconds=30,
            duration_seconds=30,
            status=ClipStatus.READY,
        )
        clip.source_video = SourceVideo(
            id="00000000-0000-0000-0000-000000000001",
            youtube_id="test123",
            channel_id="UC123",
            title="Oggy Funny Moment",
        )

        metadata = generator._fallback_metadata(clip)

        assert "caption" in metadata
        assert "description" in metadata
        assert "hashtags" in metadata
        assert "alt_text" in metadata
        assert isinstance(metadata["hashtags"], list)
        assert len(metadata["hashtags"]) <= 15

    @pytest.mark.asyncio
    async def test_validate_metadata(self, generator):
        valid = {
            "caption": "Test caption",
            "description": "Test description",
            "hashtags": ["#tag1", "#tag2"],
            "alt_text": "Test alt",
        }
        generator._validate_metadata(valid)  # Should not raise

        invalid = {"caption": "Test"}
        with pytest.raises(ValueError):
            generator._validate_metadata(invalid)

    @pytest.mark.asyncio
    async def test_validate_metadata_truncates_hashtags(self, generator):
        metadata = {
            "caption": "Test",
            "description": "Test",
            "hashtags": [f"#tag{i}" for i in range(20)],
            "alt_text": "Test",
        }
        generator._validate_metadata(metadata)
        assert len(metadata["hashtags"]) == 15