"""
modules/thumbnail_engine.py
YouTube Thumbnail Engine: Synthesizes high-CTR 1280x720 composite thumbnails
with Left-side Bold Typography (#FBBF24 highlight box) and Right-side FLUX.2 visual.
"""

import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from config import (
    logger,
    THUMB_BG,
    THUMB_HIGHLIGHT_BOX,
    THUMB_TEXT_BLACK
)

def get_font(size: int) -> ImageFont.FreeTypeFont:
    """Finds available system font or falls back to default."""
    candidates = [
        # Linux standard fonts
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        # Windows standard fonts
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

def create_composite_thumbnail(
    visual_image_path: Path,
    hook_top: str,
    hook_highlight: str,
    output_path: Path
) -> Path:
    """
    Creates a 1280x720 YouTube thumbnail:
    - Canvas: Pure Flat White (#FFFFFF)
    - Right ~55%: Resized/centered doodle visual
    - Left ~45%: High-impact typography
      * Line 1: hook_top (Solid black bold)
      * Line 2: hook_highlight (Solid black text on #FBBF24 amber highlight box)
    """
    canvas_w = 1280
    canvas_h = 720
    thumb = Image.new("RGB", (canvas_w, canvas_h), THUMB_BG)
    draw = ImageDraw.Draw(thumb)

    # 1. Place the Right-Side Visual (High-CTR 16:9 artwork filling right half)
    if visual_image_path.exists():
        try:
            from PIL import ImageOps
            vis_img = Image.open(visual_image_path).convert("RGB")
            # Fit artwork into a prominent 660x640 right container
            target_w = 660
            target_h = 640
            vis_fitted = ImageOps.fit(vis_img, (target_w, target_h), method=Image.Resampling.LANCZOS)

            pos_x = canvas_w - target_w - 30
            pos_y = (canvas_h - target_h) // 2
            thumb.paste(vis_fitted, (pos_x, pos_y))
        except Exception as e:
            logger.warning(f"Could not paste thumbnail visual: {e}")

    # 2. Typography on the Left Side (Mobile-Optimized Bold)
    font_top = get_font(84)
    MAX_TEXT_WIDTH = 520
    HIGHLIGHT_MIN_FONT = 46
    HIGHLIGHT_MAX_FONT = 76

    left_margin = 60
    start_y = 180

    # Draw hook_top
    if hook_top:
        draw.text((left_margin, start_y), hook_top.upper(), fill=THUMB_TEXT_BLACK, font=font_top)

    # Draw hook_highlight inside Amber Yellow (#FBBF24) box
    if hook_highlight:
        highlight_text = hook_highlight.upper()
        # Auto-fit: shrink font from 76 down to 46 until text fits left column
        font_highlight = get_font(HIGHLIGHT_MAX_FONT)
        highlight_size = HIGHLIGHT_MAX_FONT
        bbox = draw.textbbox((0, 0), highlight_text, font=font_highlight)
        text_w = bbox[2] - bbox[0]
        while text_w > MAX_TEXT_WIDTH and highlight_size > HIGHLIGHT_MIN_FONT:
            highlight_size -= 2
            font_highlight = get_font(highlight_size)
            bbox = draw.textbbox((0, 0), highlight_text, font=font_highlight)
            text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        box_padding_x = 24
        box_padding_y = 16
        box_top = start_y + 115
        box_left = left_margin
        box_right = box_left + text_w + (box_padding_x * 2)
        box_bottom = box_top + text_h + (box_padding_y * 2)

        # Draw highlight rounded rectangle
        draw.rounded_rectangle(
            [(box_left, box_top), (box_right, box_bottom)],
            radius=12,
            fill=THUMB_HIGHLIGHT_BOX
        )

        # Draw highlight black text
        draw.text(
            (box_left + box_padding_x, box_top + box_padding_y - 4),
            highlight_text,
            fill=THUMB_TEXT_BLACK,
            font=font_highlight
        )

    # 3. Outer Border (Protects against blending into YouTube light-theme)
    BORDER_WIDTH = 4
    BORDER_COLOR = (229, 231, 235)  # Subtle clean slate border (#E5E7EB)
    draw.rectangle([(0, 0), (canvas_w - 1, canvas_h - 1)], outline=BORDER_COLOR, width=BORDER_WIDTH)

    # 4. Save thumbnail
    thumb.save(output_path, format="PNG", quality=95)
    logger.info(f"Composite thumbnail generated -> {output_path}")
    return output_path
