"""
test_local_pipeline.py
Quick end-to-end integration test verifying all core modules:
Config -> Audio -> FLUX.2 Image -> Thumbnail -> Subtitles -> Video Assembly.
"""

import sys
import asyncio
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from config import (
    logger,
    CF_ACCOUNTS,
    GEMINI_API_KEY,
    THUMB_HIGHLIGHT_BOX
)
from modules.audio_engine import generate_single_scene_audio
from modules.image_engine import CloudflareImageRotator, generate_single_image
from modules.thumbnail_engine import create_composite_thumbnail
from modules.subtitle_engine import generate_ass_subtitles
from modules.video_engine import assemble_long_video

async def run_integration_test():
    print("=" * 70)
    print("MIELEN VOIMA LONG VIDEO ENGINE — LOCAL INTEGRATION TEST")
    print("=" * 70)

    # 1. Credentials Check
    print(f"Cloudflare Accounts Configured: {len(CF_ACCOUNTS)}")
    for acc in CF_ACCOUNTS:
        print(f"  - {acc['label']}: ID={acc['account_id'][:6]}... Token={acc['token'][:10]}...")
    print(f"Gemini API Key Configured: {'YES' if GEMINI_API_KEY else 'NO'}")

    test_dir = Path(__file__).parent / "test_output"
    test_dir.mkdir(parents=True, exist_ok=True)

    # 2. Audio Engine Test
    print("\n[Test 1/5] Testing Edge-TTS Voiceover & Trailing Silence Trim...")
    sample_scene = {
        "scene_id": 1,
        "spoken_chunk": "Korkea älykkyys kuulostaa lahjakkuudelta.",
        "full_image_prompt": (
            "Minimalist flat 2D black ink doodle on a pure white (#FFFFFF) background, "
            "thick clean outlines, lots of empty space. Character: a bare stick figure with a "
            "round white head, two black dot eyes, simple mouth line, thin black line limbs. "
            "The stick figure stands centered with a proud posture, holding up a large doodle gift box "
            "with an amber yellow (#FBBF24) ribbon on top. Short radiant doodle ray lines expand outward from the box. "
            "all subjects placed in upper 75% of frame, bottom quarter left completely empty white canvas for subtitles, "
            "clean black doodle line art, flat solid fills, family friendly."
        )
    }
    await generate_single_scene_audio(sample_scene, test_dir)
    print(f"  -> Generated audio: {sample_scene['audio_path']} (Duration: {sample_scene['duration']}s)")

    # 3. Image Engine Test (Cloudflare FLUX.2 Klein 4B)
    print("\n[Test 2/5] Testing Cloudflare FLUX.2 [klein] 4B Generation...")
    rotator = CloudflareImageRotator(CF_ACCOUNTS)
    img_path = test_dir / "scene_01.png"
    generate_single_image(sample_scene["full_image_prompt"], img_path, rotator)
    sample_scene["image_path"] = str(img_path)
    print(f"  -> Generated image: {img_path} ({img_path.stat().st_size / 1024:.1f} KB)")

    # 4. Thumbnail Engine Test
    print("\n[Test 3/5] Testing 1280x720 Composite Thumbnail...")
    thumb_path = test_dir / "thumbnail.png"
    create_composite_thumbnail(
        img_path,
        hook_top="8 MERKKIÄ",
        hook_highlight="OLETKO LIIAN ÄLYKÄS?",
        output_path=thumb_path
    )
    print(f"  -> Generated thumbnail: {thumb_path}")

    # 5. Subtitle Engine Test
    print("\n[Test 4/5] Testing ASS Subtitles (Solid Black, Outline=0)...")
    sub_path = test_dir / "subtitles.ass"
    generate_ass_subtitles([sample_scene], sub_path)
    print(f"  -> Generated subtitles: {sub_path}")

    # 6. Video Engine Test (FFmpeg TS Chunk + Concat + Subtitle Burn)
    print("\n[Test 5/5] Testing FFmpeg Memory-Safe Video Assembly...")
    final_video = test_dir / "test_sample_video.mp4"
    assemble_long_video(
        [sample_scene],
        sub_path,
        test_dir / "work",
        final_video
    )
    print(f"  -> Generated final video: {final_video} ({final_video.stat().st_size / 1024:.1f} KB)")

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED! THE LONG VIDEO RENDERING ENGINE IS 100% OPERATIONAL.")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_integration_test())
