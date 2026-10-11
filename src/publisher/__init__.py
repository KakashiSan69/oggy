from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import boto3
import httpx
from botocore.config import Config as BotoConfig

from src.config import settings
from src.db import get_session
from src.models import Clip, Post, PostStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class StorageUploader:
    def __init__(self):
        self.s3 = boto3.client(
            "s3",
            endpoint_url=settings.storage_endpoint,
            aws_access_key_id=settings.storage_access_key,
            aws_secret_access_key=settings.storage_secret_key,
            config=BotoConfig(s3={"addressing_style": "virtual"}),
        )
        self.bucket = settings.storage_bucket
        self.public_url = settings.storage_public_url.rstrip("/")

    async def upload(self, local_path: Path, remote_key: str) -> str:
        """Upload file to S3-compatible storage, return public URL."""
        content_type, _ = mimetypes.guess_type(str(local_path))
        content_type = content_type or "video/mp4"

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.s3.upload_file(
                str(local_path),
                self.bucket,
                remote_key,
                ExtraArgs={
                    "ContentType": content_type,
                    "ACL": "public-read",
                    "CacheControl": "public, max-age=31536000",
                },
            ),
        )

        return f"{self.public_url}/{remote_key}"

    async def upload_clip(self, clip: Clip) -> str:
        """Upload clip and return public URL."""
        remote_key = f"clips/{clip.source_video.youtube_id}/{clip.clip_index}.mp4"
        return await self.upload(Path(clip.local_path), remote_key)


class InstagramPublisher:
    def __init__(self):
        self.access_token = settings.ig_access_token
        self.user_id = settings.ig_user_id
        self.base_url = "https://graph.facebook.com/v20.0"

    async def create_media_container(
        self,
        video_url: str,
        caption: str,
        thumb_url: str | None = None,
    ) -> str:
        """Create media container, return container ID."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            data = {
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
                "access_token": self.access_token,
            }
            if thumb_url:
                data["thumb_url"] = thumb_url

            response = await client.post(
                f"{self.base_url}/{self.user_id}/media",
                data=data,
            )
            response.raise_for_status()
            result = response.json()
            return result["id"]

    async def wait_for_processing(self, container_id: str, max_wait: int = 300) -> bool:
        """Poll until container is ready."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            for _ in range(max_wait // 5):
                response = await client.get(
                    f"{self.base_url}/{container_id}",
                    params={"fields": "status_code", "access_token": self.access_token},
                )
                response.raise_for_status()
                status = response.json().get("status_code")

                if status == "FINISHED":
                    return True
                elif status in ("ERROR", "EXPIRED"):
                    return False

                await asyncio.sleep(5)

        return False

    async def publish_container(self, container_id: str) -> str:
        """Publish the container, return media ID."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/{self.user_id}/media_publish",
                data={
                    "creation_id": container_id,
                    "access_token": self.access_token,
                },
            )
            response.raise_for_status()
            result = response.json()
            return result["id"]

    async def get_media_permalink(self, media_id: str) -> str:
        """Get the permalink for published media."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/{media_id}",
                params={"fields": "permalink", "access_token": self.access_token},
            )
            response.raise_for_status()
            return response.json().get("permalink", "")

    async def post_reel(
        self,
        clip: Clip,
        caption: str,
        thumb_url: str | None = None,
    ) -> tuple[str, str]:
        """Full flow: create container -> wait -> publish -> get permalink."""
        container_id = await self.create_media_container(clip.storage_url, caption, thumb_url)
        logger.info(f"Created container {container_id} for clip {clip.id}")

        ready = await self.wait_for_processing(container_id)
        if not ready:
            raise RuntimeError(f"Video processing failed for container {container_id}")

        media_id = await self.publish_container(container_id)
        permalink = await self.get_media_permalink(media_id)

        return media_id, permalink


async def publish_scheduled_posts(limit: int = 10) -> int:
    """Publish posts that are scheduled and ready."""
    from sqlalchemy import select
    from src.db import get_session
    from src.models import Post, PostStatus

    now = datetime.now(timezone.utc)

    async with get_session() as session:
        result = await session.execute(
            select(Post)
            .where(
                Post.status.in_([PostStatus.SCHEDULED, PostStatus.DRAFT]),
                Post.scheduled_at <= now,
            )
            .order_by(Post.scheduled_at)
            .limit(limit)
        )
        posts = result.scalars().all()

    if not posts:
        return 0

    # Check daily limit
    async with get_session() as session:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        result = await session.execute(
            select(Post).where(
                Post.status == PostStatus.PUBLISHED,
                Post.published_at >= today_start,
            )
        )
        posted_today = len(result.scalars().all())

    if posted_today >= settings.max_posts_per_day:
        logger.info(f"Daily post limit reached ({settings.max_posts_per_day})")
        return 0

    # Check minimum interval
    async with get_session() as session:
        result = await session.execute(
            select(Post)
            .where(Post.status == PostStatus.PUBLISHED)
            .order_by(Post.published_at.desc())
            .limit(1)
        )
        last_post = result.scalar_one_or_none()

    if last_post and last_post.published_at:
        hours_since = (now - last_post.published_at).total_seconds() / 3600
        if hours_since < settings.min_hours_between_posts:
            logger.info(f"Min interval not met: {hours_since:.1f}h since last post")
            return 0

    publisher = InstagramPublisher()
    storage = StorageUploader()
    published = 0

    for post in posts:
        if published >= settings.max_posts_per_day - posted_today:
            break

        async with get_session() as session:
            post = await session.merge(post)
            post.status = PostStatus.PUBLISHING
            await session.commit()

        try:
            # Upload clip if not already uploaded
            if not post.clip.storage_url:
                storage_url = await storage.upload_clip(post.clip)
                async with get_session() as session:
                    post.clip = await session.merge(post.clip)
                    post.clip.storage_url = storage_url
                    await session.commit()
                post.clip.storage_url = storage_url

            # Build caption with hashtags
            hashtags = json.loads(post.clip.hashtags) if post.clip.hashtags else []
            full_caption = f"{post.clip.caption}\n\n{' '.join(hashtags)}"

            # Thumbnail from source video
            thumb_url = post.clip.source_video.thumbnail_url if post.clip.source_video else None

            media_id, permalink = await publisher.post_reel(
                post.clip,
                full_caption,
                thumb_url,
            )

            async with get_session() as session:
                post = await session.merge(post)
                post.status = PostStatus.PUBLISHED
                post.ig_media_id = media_id
                post.ig_permalink = permalink
                post.published_at = datetime.now(timezone.utc)
                await session.commit()

            published += 1
            logger.info(f"Published post {post.id}: {permalink}")

        except Exception as e:
            async with get_session() as session:
                post = await session.merge(post)
                post.status = PostStatus.FAILED
                post.error_message = str(e)
                await session.commit()
            logger.error(f"Failed to publish post {post.id}: {e}")

    return published