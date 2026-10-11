#!/usr/bin/env python3
"""Test video processing pipeline with a sample video."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.processor import VideoClipper, SceneDetector, ClipScorer
from src.metadata import MetadataGenerator


async def test_scene_detection(video_path: Path):
    """Test scene detection on a video file."""
    print(f"\n=== Testing Scene Detection on {video_path.name} ===")
    
    scenes = SceneDetector.detect_scenes(video_path)
    print(f"Found {len(scenes)} scenes:")
    for i, (start, end) in enumerate(scenes):
        print(f"  Scene {i+1}: {start:.2f}s - {end:.2f}s (duration: {end-start:.2f}s)")


async def test_clip_scoring(video_path: Path):
    """Test clip scoring."""
    print(f"\n=== Testing Clip Scoring ===")
    
    # Score a few segments
    test_segments = [(0, 15), (15, 30), (30, 45), (45, 60)]
    for start, end in test_segments:
        score = ClipScorer.score_segment(video_path, start, end)
        print(f"  Segment {start}s-{end}s: score = {score:.4f}")


async def test_clipping(video_path: Path, output_dir: Path):
    """Test the full clipping pipeline."""
    print(f"\n=== Testing Full Clipping Pipeline ===")
    
    clipper = VideoClipper(output_dir=output_dir)
    
    # Find best clips
    clips_data = clipper.find_best_clips(
        video_path,
        num_clips=3,
        min_duration=15,
        max_duration=60,
    )
    
    print(f"Selected {len(clips_data)} clips:")
    for start, end, score in clips_data:
        print(f"  {start:.2f}s - {end:.2f}s (score: {score:.4f})")
    
    # Mock a source video for extraction
    class MockSourceVideo:
        def __init__(self, path):
            self.id = "test-id"
            self.youtube_id = "test123"
            self.local_path = str(path)
    
    source = MockSourceVideo(video_path)
    
    # Extract clips (this will fail without FFmpeg/MoviePy in test env)
    print("\nAttempting to extract clips...")
    try:
        created = await clipper.extract_clips(source, clips_data)
        print(f"Created {len(created)} clips:")
        for clip in created:
            print(f"  Clip {clip.clip_index}: {clip.local_path} ({clip.file_size_bytes} bytes)")
    except Exception as e:
        print(f"[Expected in test env] Extraction failed: {e}")


async def test_metadata_generation():
    """Test metadata generation with fallback."""
    print(f"\n=== Testing Metadata Generation ===")
    
    generator = MetadataGenerator()
    
    class MockClip:
        def __init__(self):
            self.duration_seconds = 30
            self.start_seconds = 10
            self.end_seconds = 40
            class SourceVideo:
                title = "Oggy and the Cockroaches - Funny Compilation"
            self.source_video = SourceVideo()
    
    class SourceVideo:
        pass
    
    clip = MockClip()
    metadata = generator._fallback_metadata(clip)
    
    print("Fallback metadata:")
    print(f"  Caption: {metadata['caption']}")
    print(f"  Description: {metadata['description']}")
    print(f"  Hashtags ({len(metadata['hashtags'])}): {', '.join(metadata['hashtags'][:5])}...")
    print(f"  Alt text: {metadata['alt_text']}")


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Test video processing pipeline")
    parser.add_argument("video", nargs="?", help="Path to test video file")
    parser.add_argument("--output", "-o", default="./test_output", help="Output directory")
    args = parser.parse_args()
    
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if args.video:
        video_path = Path(args.video)
        if not video_path.exists():
            print(f"Video not found: {video_path}")
            return
        
        await test_scene_detection(video_path)
        await test_clip_scoring(video_path)
        await test_clipping(video_path, output_dir)
    else:
        print("No video provided. Testing metadata generation only.")
    
    await test_metadata_generation()
    print("\n=== All tests completed ===")


if __name__ == "__main__":
    asyncio.run(main())