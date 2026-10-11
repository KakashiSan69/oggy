from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from src.config import settings

if TYPE_CHECKING:
    from src.models import Clip

logger = logging.getLogger(__name__)


PROMPT_TEMPLATE = """
You are creating Instagram Reel metadata for an Oggy and the Cockroaches cartoon clip.

Clip context: {description}
Duration: {duration} seconds
Key visual moments: {key_frames}

Create engaging metadata for Instagram Reels. The audience loves funny cartoon moments, nostalgia, and relatable humor.

Return ONLY valid JSON with this exact structure:
{
  "caption": "Hook in first sentence (max 125 chars before truncation). Add 2-3 relevant emojis. Example: 'When the cockroaches steal Oggy's snack 😂🪳🍕'",
  "description": "Longer description (2-3 sentences). Include context about the episode/scene, credit to official channel, and a call-to-action like 'Follow for more Oggy moments!'",
  "hashtags": ["#oggy", "#oggyandthecockroaches", "#cartoons", "#funnyclips", "#nostalgia", "#animation", "#fyp", "#reels", "#viral", "#cartoonnetwork"],
  "alt_text": "Accessibility description of the visual content for screen readers"
}

Rules:
- Caption must be engaging, first sentence hooks viewer
- Hashtags: exactly 10-15 tags, mix of broad and niche
- Alt text: describe visual action for accessibility
- No markdown, no extra text, just JSON
"""


class MetadataGenerator:
    def __init__(self):
        self.provider = settings.llm_provider
        self.client = self._create_client()

    def _create_client(self):
        if self.provider == "openai":
            from openai import AsyncOpenAI
            return AsyncOpenAI(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
            )
        elif self.provider == "anthropic":
            from anthropic import AsyncAnthropic
            return AsyncAnthropic(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
            )
        elif self.provider == "ollama":
            from openai import AsyncOpenAI
            return AsyncOpenAI(
                api_key="ollama",
                base_url=settings.llm_base_url or "http://host.docker.internal:11434/v1",
            )
        raise ValueError(f"Unknown LLM provider: {self.provider}")

    async def generate(self, clip: Clip, source_description: str = "") -> dict:
        """Generate metadata for a clip."""
        prompt = PROMPT_TEMPLATE.format(
            description=source_description or clip.source_video.title if clip.source_video else "Oggy cartoon clip",
            duration=clip.duration_seconds,
            key_frames=f"Clip from {clip.start_seconds:.0f}s to {clip.end_seconds:.0f}s of source video",
        )

        try:
            if self.provider in ("openai", "ollama"):
                response = await self.client.chat.completions.create(
                    model=settings.llm_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=500,
                    response_format={"type": "json_object"},
                )
                content = response.choices[0].message.content
            elif self.provider == "anthropic":
                response = await self.client.messages.create(
                    model=settings.llm_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=500,
                )
                content = response.content[0].text
            else:
                raise ValueError(f"Unknown provider: {self.provider}")

            metadata = json.loads(content)
            self._validate_metadata(metadata)
            return metadata

        except Exception as e:
            logger.error(f"LLM generation failed: {e}, using fallback")
            return self._fallback_metadata(clip)

    def _validate_metadata(self, metadata: dict) -> None:
        required = ["caption", "description", "hashtags", "alt_text"]
        for key in required:
            if key not in metadata:
                raise ValueError(f"Missing required field: {key}")
        if not isinstance(metadata["hashtags"], list):
            raise ValueError("Hashtags must be a list")
        if len(metadata["hashtags"]) > 15:
            metadata["hashtags"] = metadata["hashtags"][:15]

    def _fallback_metadata(self, clip: Clip) -> dict:
        return {
            "caption": "Oggy and the cockroaches at it again! 😂🪳",
            "description": "Classic Oggy and the Cockroaches moment. The cockroaches never give up! Follow for more nostalgic cartoon clips.",
            "hashtags": [
                "#oggy", "#oggyandthecockroaches", "#cartoons", "#funnyclips",
                "#nostalgia", "#animation", "#fyp", "#reels", "#viral",
                "#cartoonnetwork", "#childhood", "#memes", "#funny", "#shorts"
            ],
            "alt_text": "Animated clip from Oggy and the Cockroaches showing Oggy the blue cat dealing with three mischievous cockroaches.",
        }


async def generate_metadata_for_clips(limit: int = 20) -> int:
    """Generate metadata for clips that don't have it yet."""
    from sqlalchemy import select
    from src.db import get_session
    from src.models import Clip, ClipStatus

    async with get_session() as session:
        result = await session.execute(
            select(Clip)
            .where(
                Clip.status == ClipStatus.READY,
                (Clip.caption.is_(None) | (Clip.caption == ""))
            )
            .order_by(Clip.created_at)
            .limit(limit)
        )
        clips = result.scalars().all()

    if not clips:
        return 0

    generator = MetadataGenerator()
    generated = 0

    for clip in clips:
        try:
            source_desc = clip.source_video.title if clip.source_video else ""
            if clip.source_video and clip.source_video.description:
                source_desc += f" - {clip.source_video.description[:200]}"

            metadata = await generator.generate(clip, source_desc)

            async with get_session() as session:
                clip = await session.merge(clip)
                clip.caption = metadata["caption"]
                clip.description = metadata["description"]
                clip.hashtags = json.dumps(metadata["hashtags"])
                clip.alt_text = metadata["alt_text"]
                await session.commit()

            generated += 1
            logger.info(f"Generated metadata for clip {clip.id}")

        except Exception as e:
            logger.error(f"Failed to generate metadata for clip {clip.id}: {e}")

    return generated