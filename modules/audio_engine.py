"""
modules/audio_engine.py
Edge-TTS Audio Engine: Generates Finnish speech with HarriNeural,
measures exact duration, and trims trailing silence with anti-pop micro fade-out.
"""

import os
import asyncio
import edge_tts
from pathlib import Path
from typing import List, Dict, Any
from pydub import AudioSegment
from pydub.silence import detect_leading_silence

from config import (
    logger,
    VOICE_DEFAULT,
    VOICE_RATE,
    AUDIO_TRAILING_GAP_MS,
    AUDIO_MICRO_FADE_OUT_MS
)

def trim_leading_silence(
    audio: AudioSegment,
    silence_threshold: float = -42.0,
    keep_lead_ms: int = 50
) -> AudioSegment:
    """
    Trims leading dead air (Edge-TTS adds 200-350ms per sentence) while
    retaining a clean 40-50ms lead-in buffer so speech onset is never clipped.
    """
    leading_silence = detect_leading_silence(audio, silence_threshold=silence_threshold)
    if leading_silence > keep_lead_ms:
        return audio[leading_silence - keep_lead_ms:]
    return audio


def trim_trailing_silence(
    audio: AudioSegment,
    silence_threshold: float = -42.0,
    keep_gap_ms: int = AUDIO_TRAILING_GAP_MS,
    fade_out_ms: int = AUDIO_MICRO_FADE_OUT_MS
) -> AudioSegment:
    """
    Trims silence from BOTH ends: leading dead air (keeping ~50ms lead-in)
    plus trailing silence (keeping `keep_gap_ms`, default 100ms) with a
    micro fade-out to avoid pop artifacts.
    """
    # 1. Trim leading silence first (Edge-TTS 200-350ms dead air per scene).
    audio = trim_leading_silence(
        audio, silence_threshold=silence_threshold, keep_lead_ms=50
    )

    # 2. Trim trailing silence via reversed-stream detection.
    rev = audio.reverse()
    trailing_silence = detect_leading_silence(rev, silence_threshold=silence_threshold)

    if trailing_silence > keep_gap_ms:
        trimmed_rev = rev[trailing_silence - keep_gap_ms:]
        trimmed = trimmed_rev.reverse()
        return trimmed.fade_out(fade_out_ms)

    return audio.fade_out(fade_out_ms)

async def generate_single_scene_audio(
    scene: Dict[str, Any],
    output_dir: Path
) -> Dict[str, Any]:
    """Generates trimmed Finnish audio for a single scene item."""
    scene_id = scene["scene_id"]
    text = scene["spoken_chunk"]
    raw_path = output_dir / f"scene_{scene_id:02d}_raw.mp3"
    final_path = output_dir / f"scene_{scene_id:02d}.wav"

    # Step 1: Synthesize with Edge TTS (3 attempts, 45s timeout, exp backoff)
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            communicate = edge_tts.Communicate(text, VOICE_DEFAULT, rate=VOICE_RATE)
            await asyncio.wait_for(communicate.save(str(raw_path)), timeout=45)
            last_err = None
            break
        except Exception as e:
            last_err = e
            logger.warning(
                f"[Scene {scene_id}] TTS attempt {attempt + 1}/3 failed: {e}"
            )
            if attempt < 2:
                await asyncio.sleep(2 ** (attempt + 1))
    if last_err is not None:
        raise RuntimeError(
            f"Edge-TTS failed for scene {scene_id} after 3 attempts: {last_err}"
        ) from last_err

    # Step 2: Load, trim leading + trailing silence & save uncompressed WAV
    audio_seg = AudioSegment.from_file(str(raw_path))
    trimmed_seg = trim_trailing_silence(audio_seg)
    trimmed_seg.export(str(final_path), format="wav")

    # Clean up raw file
    if raw_path.exists():
        raw_path.unlink()

    duration_sec = round(len(trimmed_seg) / 1000.0, 3)
    scene["audio_path"] = str(final_path)
    scene["duration"] = duration_sec

    return scene

async def generate_all_audio(
    scenes: List[Dict[str, Any]],
    output_dir: Path
) -> List[Dict[str, Any]]:
    """Generates audio for all scenes sequentially to prevent socket exhaustion."""
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Generating Finnish voiceover for {len(scenes)} scenes...")

    for i, scene in enumerate(scenes):
        await generate_single_scene_audio(scene, output_dir)
        if (i + 1) % 10 == 0 or (i + 1) == len(scenes):
            logger.info(f"  Processed audio {i + 1}/{len(scenes)} scenes")

        # Anti-abuse cooldown: 2s pause between WebSocket connections to prevent 403 blocks
        if i + 1 < len(scenes):
            await asyncio.sleep(2.0)

    total_duration = sum(s["duration"] for s in scenes)
    logger.info(f"All audio generated! Total video duration: {total_duration:.2f}s ({total_duration/60:.2f} min)")
    return scenes
