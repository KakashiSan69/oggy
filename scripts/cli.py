#!/usr/bin/env python3
"""CLI tool for manual operations."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import click
from rich.console import Console
from rich.table import Table

from src.config import settings
from src.db import init_db, get_session
from src.discovery import run_discovery
from src.downloader import download_pending_videos
from src.processor import process_pending_clips
from src.metadata import generate_metadata_for_clips
from src.publisher import publish_scheduled_posts
from src.cleanup import cleanup_old_files
from src.scheduler import get_job_status
from src.models import SourceVideo, Clip, Post, VideoStatus, ClipStatus, PostStatus
from sqlalchemy import select, func


console = Console()


@click.group()
def cli():
    """Oggy Reels Bot - Manual Operations CLI"""
    pass


@cli.command()
def status():
    """Show system status and statistics."""
    async def _status():
        await init_db()
        
        async with get_session() as session:
            # Source videos
            sv_table = Table(title="Source Videos")
            sv_table.add_column("Status", style="cyan")
            sv_table.add_column("Count", style="green")
            
            for status in VideoStatus:
                result = await session.execute(
                    select(func.count(SourceVideo.id)).where(SourceVideo.status == status)
                )
                sv_table.add_row(status.value, str(result.scalar()))
            
            console.print(sv_table)
            
            # Clips
            clip_table = Table(title="Clips")
            clip_table.add_column("Status", style="cyan")
            clip_table.add_column("Count", style="green")
            
            for status in ClipStatus:
                result = await session.execute(
                    select(func.count(Clip.id)).where(Clip.status == status)
                )
                clip_table.add_row(status.value, str(result.scalar()))
            
            console.print(clip_table)
            
            # Posts
            post_table = Table(title="Posts")
            post_table.add_column("Status", style="cyan")
            post_table.add_column("Count", style="green")
            
            for status in PostStatus:
                result = await session.execute(
                    select(func.count(Post.id)).where(Post.status == status)
                )
                post_table.add_row(status.value, str(result.scalar()))
            
            console.print(post_table)
            
            # Today's posts
            from datetime import datetime, timezone
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            result = await session.execute(
                select(func.count(Post.id)).where(
                    Post.status == PostStatus.PUBLISHED,
                    Post.published_at >= today_start,
                )
            )
            console.print(f"\n[bold]Posts published today:[/bold] {result.scalar()} / {settings.max_posts_per_day}")

    asyncio.run(_status())


@cli.command()
def jobs():
    """Show scheduled jobs."""
    from src.scheduler import setup_scheduler
    scheduler = setup_scheduler()
    
    table = Table(title="Scheduled Jobs")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Next Run", style="yellow")
    table.add_column("Trigger", style="magenta")
    
    for job in scheduler.get_jobs():
        table.add_row(
            job.id,
            job.name,
            job.next_run_time.isoformat() if job.next_run_time else "N/A",
            str(job.trigger)
        )
    
    console.print(table)


@cli.command()
@click.option('--limit', default=10, help='Max videos to process')
def discover(limit):
    """Run video discovery manually."""
    async def _discover():
        await init_db()
        console.print("Running discovery...")
        count = await run_discovery()
        console.print(f"[green]Discovered {count} new videos[/green]")
    
    asyncio.run(_discover())


@cli.command()
@click.option('--limit', default=10, help='Max videos to download')
def download(limit):
    """Download pending videos."""
    async def _download():
        await init_db()
        console.print("Downloading videos...")
        count = await download_pending_videos(limit)
        console.print(f"[green]Downloaded {count} videos[/green]")
    
    asyncio.run(_download())


@cli.command()
@click.option('--limit', default=5, help='Max videos to process')
def process(limit):
    """Process videos into clips."""
    async def _process():
        await init_db()
        console.print("Processing videos...")
        count = await process_pending_clips(limit)
        console.print(f"[green]Created {count} clips[/green]")
    
    asyncio.run(_process())


@cli.command()
@click.option('--limit', default=20, help='Max clips to generate metadata for')
def metadata(limit):
    """Generate metadata for clips."""
    async def _metadata():
        await init_db()
        console.print("Generating metadata...")
        count = await generate_metadata_for_clips(limit)
        console.print(f"[green]Generated metadata for {count} clips[/green]")
    
    asyncio.run(_metadata())


@cli.command()
@click.option('--limit', default=10, help='Max posts to publish')
def publish(limit):
    """Publish scheduled posts."""
    async def _publish():
        await init_db()
        console.print("Publishing posts...")
        count = await publish_scheduled_posts(limit)
        console.print(f"[green]Published {count} posts[/green]")
    
    asyncio.run(_publish())


@cli.command()
def cleanup():
    """Run cleanup."""
    async def _cleanup():
        await init_db()
        console.print("Running cleanup...")
        result = await cleanup_old_files()
        console.print(f"[green]Cleanup complete:[/green] {result}")
    
    asyncio.run(_cleanup())


@cli.command()
@click.argument('job_id')
def trigger(job_id):
    """Trigger a scheduled job manually."""
    from src.scheduler import scheduler
    
    job = scheduler.get_job(job_id)
    if not job:
        console.print(f"[red]Job '{job_id}' not found[/red]")
        sys.exit(1)
    
    job.modify(next_run_time=None)
    console.print(f"[green]Triggered job: {job_id}[/green]")


@cli.command()
@click.argument('youtube_id')
def inspect(youtube_id):
    """Inspect a source video by YouTube ID."""
    async def _inspect():
        await init_db()
        
        async with get_session() as session:
            result = await session.execute(
                select(SourceVideo).where(SourceVideo.youtube_id == youtube_id)
            )
            video = result.scalar_one_or_none()
            
            if not video:
                console.print(f"[red]Video not found: {youtube_id}[/red]")
                return
            
            console.print(f"[bold]Source Video:[/bold] {video.title}")
            console.print(f"  ID: {video.id}")
            console.print(f"  YouTube ID: {video.youtube_id}")
            console.print(f"  Channel: {video.channel_id}")
            console.print(f"  Status: {video.status.value}")
            console.print(f"  Discovered: {video.discovered_at}")
            console.print(f"  Downloaded: {video.downloaded_at}")
            console.print(f"  Local Path: {video.local_path}")
            console.print(f"  File Size: {video.file_size_bytes} bytes")
            
            if video.error_message:
                console.print(f"  [red]Error: {video.error_message}[/red]")
            
            # Show clips
            result = await session.execute(
                select(Clip).where(Clip.source_video_id == video.id)
            )
            clips = result.scalars().all()
            
            if clips:
                console.print(f"\n[bold]Clips ({len(clips)}):[/bold]")
                for clip in clips:
                    console.print(f"  Clip {clip.clip_index}: {clip.start_seconds:.1f}s - {clip.end_seconds:.1f}s ({clip.duration_seconds:.1f}s)")
                    console.print(f"    Status: {clip.status.value}")
                    console.print(f"    Path: {clip.local_path}")
                    console.print(f"    Storage: {clip.storage_url}")
                    if clip.caption:
                        console.print(f"    Caption: {clip.caption[:80]}...")
    
    asyncio.run(_inspect())


if __name__ == "__main__":
    cli()