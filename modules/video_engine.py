"""
modules/video_engine.py
FFmpeg Video Engine: Memory-Safe chunk rendering (.ts segments) under 512MB RAM,
fast stream-copy concatenation, and burning in solid black ASS subtitles.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Any

from config import (
    logger,
    VIDEO_WIDTH,
    VIDEO_HEIGHT,
    VIDEO_FPS
)

def render_scene_ts_chunk(
    image_path: Path,
    audio_path: Path,
    duration: float,
    output_ts_path: Path
) -> bool:
    """
    Renders a single scene to a transport stream (.ts) segment.
    Uses minimal memory (<80MB RAM) by processing one short clip at a time.
    """
    # Video filter: Scale & pad to 1920x1080 with pure white background #FFFFFF
    vf = (
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=white,"
        f"format=yuv420p"
    )

    cmd = [
        "ffmpeg", "-nostdin", "-loglevel", "error", "-y",
        "-loop", "1", "-t", str(duration), "-i", str(image_path),
        "-i", str(audio_path),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-threads", "1",
        "-r", str(VIDEO_FPS),
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
        "-shortest",
        "-f", "mpegts",
        str(output_ts_path)
    ]

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=180)
    if res.returncode != 0:
        logger.error(f"FFmpeg chunk error on {output_ts_path.name}:\n{res.stderr[-400:]}")
        raise RuntimeError(f"FFmpeg failed to render {output_ts_path.name}")

    return True

def assemble_long_video(
    scenes: List[Dict[str, Any]],
    ass_subtitle_path: Path,
    work_dir: Path,
    final_output_path: Path
) -> Path:
    """
    Complete video assembly pipeline:
    1. Render .ts chunk per scene (Low RAM safe)
    2. Concat all .ts chunks into raw MP4 (Stream copy, instant)
    3. Burn in ASS subtitles (clean solid black text)
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    ts_dir = work_dir / "ts_segments"
    ts_dir.mkdir(parents=True, exist_ok=True)

    ts_files = []
    logger.info(f"Rendering {len(scenes)} memory-safe TS video segments...")

    for i, scene in enumerate(scenes):
        scene_id = scene["scene_id"]
        img_path = Path(scene["image_path"])
        aud_path = Path(scene["audio_path"])
        dur = scene["duration"]
        ts_path = ts_dir / f"seg_{scene_id:02d}.ts"

        render_scene_ts_chunk(img_path, aud_path, dur, ts_path)
        ts_files.append(ts_path)

        if (i + 1) % 10 == 0 or (i + 1) == len(scenes):
            logger.info(f"  Rendered {i + 1}/{len(scenes)} TS segments")

    # Step 2: Create concat list and concatenate
    concat_list_path = work_dir / "concat_list.txt"
    with open(concat_list_path, "w", encoding="utf-8") as f:
        for p in ts_files:
            # Use forward slashes for FFmpeg compatibility
            f.write(f"file '{p.resolve().as_posix()}'\n")

    raw_mp4 = work_dir / "assembled_raw.mp4"
    logger.info("Concatenating TS segments via stream copy...")
    concat_cmd = [
        "ffmpeg", "-nostdin", "-loglevel", "error", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list_path),
        "-c", "copy",
        str(raw_mp4)
    ]
    res_concat = subprocess.run(concat_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=600)
    if res_concat.returncode != 0:
        logger.error(f"FFmpeg concat error:\n{res_concat.stderr[-400:]}")
        raise RuntimeError("FFmpeg concat failed")

    # Step 3: Burn in ASS Subtitles
    logger.info(f"Burning in ASS subtitles from {ass_subtitle_path.name}...")
    # Escape path for FFmpeg filter on Windows and Linux
    sub_path_escaped = str(ass_subtitle_path.resolve()).replace("\\", "/").replace(":", "\\:")
    burn_cmd = [
        "ffmpeg", "-nostdin", "-loglevel", "error", "-y",
        "-i", str(raw_mp4),
        "-vf", f"ass='{sub_path_escaped}'",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-threads", "1",
        "-c:a", "copy",
        str(final_output_path)
    ]

    res_burn = subprocess.run(burn_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=600)
    if res_burn.returncode != 0:
        logger.error(f"FFmpeg subtitle burn error:\n{res_burn.stderr[-400:]}")
        raise RuntimeError("FFmpeg subtitle burning failed")

    # Clean up intermediate raw mp4 and ts directory to save disk space
    if raw_mp4.exists():
        raw_mp4.unlink()
    shutil.rmtree(ts_dir, ignore_errors=True)

    file_size_mb = final_output_path.stat().st_size / (1024 * 1024)
    logger.info(f"Final subtitled long video created! Size: {file_size_mb:.2f} MB -> {final_output_path.name}")
    return final_output_path
