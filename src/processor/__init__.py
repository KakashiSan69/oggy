from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np
from scenedetect import detect, ContentDetector

from src.config import settings
from src.db import get_session
from src.models import Clip, ClipStatus, SourceVideo, VideoStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class SceneDetector:
    @staticmethod
    def detect_scenes(video_path: Path, threshold: float = 30.0) -> list[tuple[float, float]]:
        """Detect scene boundaries, return list of (start_sec, end_sec)."""
        scene_list = detect(str(video_path), ContentDetector(threshold=threshold))
        return [(start.get_seconds(), end.get_seconds()) for start, end in scene_list]


class ClipScorer:
    """Score video segments for 'interestingness'."""

    @staticmethod
    def score_segment(
        video_path: Path,
        start_sec: float,
        end_sec: float,
        sample_rate: int = 2,
    ) -> float:
        """Score based on motion, color variance, and audio energy."""
        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        start_frame = int(start_sec * fps)
        end_frame = int(end_sec * fps)
        frame_step = max(1, int(fps / sample_rate))

        motion_scores = []
        color_scores = []
        prev_frame = None

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        for frame_idx in range(start_frame, min(end_frame, total_frames), frame_step):
            ret, frame = cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, (160, 90))

            if prev_frame is not None:
                diff = cv2.absdiff(prev_frame, gray)
                motion_scores.append(np.mean(diff))

            color_var = np.var(frame.reshape(-1, 3), axis=0).mean()
            color_scores.append(color_var)
            prev_frame = gray

        cap.release()

        motion_score = np.mean(motion_scores) if motion_scores else 0
        color_score = np.mean(color_scores) if color_scores else 0

        # Normalize and combine
        norm_motion = min(motion_score / 50.0, 1.0)
        norm_color = min(color_score / 1000.0, 1.0)

        return (norm_motion * 0.7 + norm_color * 0.3)


class VideoClipper:
    def __init__(self, output_dir: Path | None = None):
        self.output_dir = output_dir or settings.data_dir / "clips"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def find_best_clips(
        self,
        video_path: Path,
        num_clips: int = 3,
        min_duration: int = 15,
        max_duration: int = 60,
    ) -> list[tuple[float, float, float]]:
        """Find best clips, return list of (start, end, score)."""
        scenes = SceneDetector.detect_scenes(video_path)
        if not scenes:
            # Fallback: split video into equal segments
            duration = self._get_duration(video_path)
            segment_len = max_duration
            scenes = [(i * segment_len, min((i + 1) * segment_len, duration)) for i in range(num_clips)]

        scored_clips = []
        for start, end in scenes:
            duration = end - start
            if duration < min_duration:
                continue
            if duration > max_duration:
                # Split long scenes
                num_parts = int(np.ceil(duration / max_duration))
                for i in range(num_parts):
                    s = start + i * max_duration
                    e = min(s + max_duration, end)
                    if e - s >= min_duration:
                        score = ClipScorer.score_segment(video_path, s, e)
                        scored_clips.append((s, e, score))
            else:
                score = ClipScorer.score_segment(video_path, start, end)
                scored_clips.append((start, end, score))

        # Sort by score descending, take top N non-overlapping
        scored_clips.sort(key=lambda x: x[2], reverse=True)

        selected = []
        for start, end, score in scored_clips:
            overlap = any(
                not (end <= s or start >= e) for s, e, _ in selected
            )
            if not overlap:
                selected.append((start, end, score))
                if len(selected) >= num_clips:
                    break

        return selected

    def _get_duration(self, video_path: Path) -> float:
        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        return frames / fps if fps > 0 else 0

    async def extract_clips(
        self,
        source_video: SourceVideo,
        clips_data: list[tuple[float, float, float]],
    ) -> list[Clip]:
        """Extract clips using FFmpeg."""
        from moviepy.editor import VideoFileClip

        created_clips = []

        for idx, (start, end, score) in enumerate(clips_data):
            clip = Clip(
                source_video_id=source_video.id,
                clip_index=idx,
                start_seconds=start,
                end_seconds=end,
                duration_seconds=end - start,
                status=ClipStatus.PROCESSING,
            )

            async with get_session() as session:
                session.add(clip)
                await session.commit()
                await session.refresh(clip)

            output_path = self.output_dir / f"{source_video.youtube_id}_clip{idx}.mp4"

            try:
                await self._extract_clip_ffmpeg(
                    Path(source_video.local_path),
                    output_path,
                    start,
                    end,
                )

                # Resize to 9:16, add watermark
                final_path = await self._process_for_reels(output_path)

                async with get_session() as session:
                    clip = await session.merge(clip)
                    clip.status = ClipStatus.READY
                    clip.local_path = str(final_path)
                    clip.file_size_bytes = final_path.stat().st_size
                    clip.processed_at = datetime.now(timezone.utc)
                    await session.commit()

                created_clips.append(clip)
                logger.info(f"Created clip {clip.id}: {start:.1f}s-{end:.1f}s (score: {score:.2f})")

            except Exception as e:
                async with get_session() as session:
                    clip = await session.merge(clip)
                    clip.status = ClipStatus.FAILED
                    clip.error_message = str(e)
                    await session.commit()
                logger.error(f"Failed to create clip {idx} for {source_video.youtube_id}: {e}")

        return created_clips

    async def _extract_clip_ffmpeg(
        self,
        input_path: Path,
        output_path: Path,
        start: float,
        end: float,
    ) -> None:
        duration = end - start
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", str(input_path),
            "-t", str(duration),
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", str(settings.video_crf),
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            str(output_path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {stderr.decode()}")

    async def _process_for_reels(self, input_path: Path) -> Path:
        """Resize to 9:16, add padding/watermark."""
        from moviepy.editor import VideoFileClip, CompositeVideoClip, ImageClip

        output_path = input_path.with_name(f"{input_path.stem}_reels.mp4")

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._process_reels_sync, input_path, output_path)
        return output_path

    def _process_reels_sync(self, input_path: Path, output_path: Path) -> None:
        target_w, target_h = settings.target_width, settings.target_height

        with VideoFileClip(str(input_path)) as clip:
            # Resize maintaining aspect, pad to 9:16
            clip_ratio = clip.w / clip.h
            target_ratio = target_w / target_h

            if clip_ratio > target_ratio:
                # Wider than 9:16 - fit width, pad top/bottom
                new_w = target_w
                new_h = int(target_w / clip_ratio)
            else:
                # Taller than 9:16 - fit height, pad sides
                new_h = target_h
                new_w = int(target_h * clip_ratio)

            resized = clip.resize((new_w, new_h))

            # Create background (black)
            from moviepy.editor import ColorClip
            bg = ColorClip((target_w, target_h), color=(0, 0, 0), duration=clip.duration)

            # Center the video
            x = (target_w - new_w) // 2
            y = (target_h - new_h) // 2
            final = CompositeVideoClip([bg, resized.set_position((x, y))])

            # Add watermark if configured
            if settings.watermark_path and Path(settings.watermark_path).exists():
                wm = ImageClip(settings.watermark_path).set_duration(clip.duration)
                wm = wm.resize(height=int(target_h * 0.1)).set_opacity(settings.watermark_opacity)
                wm = wm.set_position(("right", "bottom")).margin(20, opacity=0)
                final = CompositeVideoClip([final, wm])

            final.write_videofile(
                str(output_path),
                fps=settings.target_fps,
                codec="libx264",
                preset="medium",
                ffmpeg_params=["-crf", str(settings.video_crf), "-movflags", "+faststart"],
                audio_codec="aac",
                logger=None,
            )


async def process_pending_clips(limit: int = 5) -> int:
    """Process pending clips from downloaded videos."""
    from sqlalchemy import select

    async with get_session() as session:
        result = await session.execute(
            select(SourceVideo)
            .where(SourceVideo.status == VideoStatus.DOWNLOADED)
            .order_by(SourceVideo.downloaded_at)
            .limit(limit)
        )
        videos = result.scalars().all()

    if not videos:
        return 0

    clipper = VideoClipper()
    total_clips = 0

    for video in videos:
        if not video.local_path or not Path(video.local_path).exists():
            continue

        clips_data = clipper.find_best_clips(
            Path(video.local_path),
            num_clips=settings.clips_per_source,
            min_duration=settings.clip_min_duration,
            max_duration=settings.clip_max_duration,
        )

        if clips_data:
            created = await clipper.extract_clips(video, clips_data)
            total_clips += len(created)

    return total_clips