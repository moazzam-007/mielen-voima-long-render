"""
modules/subtitle_engine.py
ASS Subtitle Engine: Generates pure solid black subtitles with ZERO white outline,
centered bottom alignment, and word wrapping for 1080p video.
"""

from pathlib import Path
from typing import List, Dict, Any

from config import logger, SUBTITLE_STYLE

def format_ass_time(seconds: float) -> str:
    """Formats seconds into ASS timestamp format: H:MM:SS.cs"""
    total_cs = int(round(seconds * 100))
    hrs = total_cs // 360000
    mins = (total_cs % 360000) // 6000
    secs = (total_cs % 6000) // 100
    csecs = total_cs % 100
    return f"{hrs}:{mins:02d}:{secs:02d}.{csecs:02d}"

def escape_ass_text(text: str) -> str:
    """Escapes ASS override-block characters so literal { } render safely."""
    return text.replace("{", "\\{").replace("}", "\\}")


def wrap_text(text: str, max_chars_per_line: int = 42) -> str:
    """Splits long sentences into 1-2 balanced lines with ASS line breaks."""
    text = escape_ass_text(text)
    words = text.split()
    if len(text) <= max_chars_per_line or len(words) <= 5:
        return text

    # Handle a single very long Finnish word: hard-break it.
    if len(words) == 1 and len(text) > max_chars_per_line:
        return f"{text[:max_chars_per_line]}\\N{text[max_chars_per_line:]}"

    # Balance by character count (not word count) for even two-line layout.
    total_chars = sum(len(w) for w in words)
    best_mid = len(words) // 2
    best_diff = None
    running = 0
    for i in range(1, len(words)):
        running += len(words[i - 1]) + 1  # +1 for the space
        diff = abs((total_chars / 2) - running)
        if best_diff is None or diff < best_diff:
            best_diff = diff
            best_mid = i

    line1 = " ".join(words[:best_mid])
    line2 = " ".join(words[best_mid:])

    # Hard-break any remaining overlong line caused by agglutinative compounds.
    if len(line1) > max_chars_per_line * 2 or len(line2) > max_chars_per_line * 2:
        long_line = line1 if len(line1) > len(line2) else line2
        chunks = [long_line[i:i + max_chars_per_line] for i in range(0, len(long_line), max_chars_per_line)]
        if len(long_line) == len(line1):
            return f"{chunks[0]}\\N{' '.join(chunks[1:] + [line2])}" if len(chunks) > 1 else f"{line1}\\N{line2}"
        return f"{line1}\\N{chunks[0]} {' '.join(chunks[1:])}" if len(chunks) > 1 else f"{line1}\\N{line2}"

    return f"{line1}\\N{line2}"

def generate_ass_subtitles(
    scenes: List[Dict[str, Any]],
    output_path: Path
) -> Path:
    """
    Generates an Advanced SubStation Alpha (.ass) file with:
    - Pure solid black font (#000000)
    - Outline = 0, Shadow = 0 (No white stroke or border)
    - Centered bottom alignment
    """
    ass_header = f"""[Script Info]
Title: Mielen Voima Long Video Subtitles
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{SUBTITLE_STYLE['Fontname']},{SUBTITLE_STYLE['Fontsize']},{SUBTITLE_STYLE['PrimaryColour']},&H000000FF,{SUBTITLE_STYLE['OutlineColour']},{SUBTITLE_STYLE['BackColour']},{SUBTITLE_STYLE['Bold']},0,0,0,100,100,0,0,{SUBTITLE_STYLE['BorderStyle']},{SUBTITLE_STYLE['Outline']},{SUBTITLE_STYLE['Shadow']},{SUBTITLE_STYLE['Alignment']},100,100,{SUBTITLE_STYLE['MarginV']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    current_time = 0.0
    dialogue_lines = []

    for scene in scenes:
        start_t = current_time
        duration = scene.get("duration", 3.0)
        end_t = start_t + duration
        current_time = end_t

        start_str = format_ass_time(start_t)
        end_str = format_ass_time(end_t)

        raw_text = scene.get("spoken_chunk", "").strip()
        formatted_text = wrap_text(raw_text)

        dialogue_lines.append(
            f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{formatted_text}"
        )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ass_header + "\n".join(dialogue_lines) + "\n")

    logger.info(f"Generated ASS subtitles with {len(dialogue_lines)} cues -> {output_path.name}")
    return output_path
