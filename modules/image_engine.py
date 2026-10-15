"""
modules/image_engine.py
Cloudflare AI FLUX.2 [klein] 4B Engine: Generates whiteboard illustrations
with 3-account rotation, JSON payload, Pillow normalization, and automatic failover.
"""

import os
import io
import time
import base64
import requests
from pathlib import Path
from typing import List, Dict, Any
from PIL import Image

from config import (
    logger,
    CF_ACCOUNTS,
    CF_MODEL,
    CF_THUMBNAIL_MODEL,
    IMG_WIDTH,
    IMG_HEIGHT
)

class CloudflareImageRotator:
    def __init__(self, accounts: List[Dict[str, str]]):
        self.accounts = accounts
        self.current_idx = 0

    def get_current(self) -> Dict[str, str]:
        if not self.accounts:
            raise RuntimeError("No Cloudflare accounts available!")
        return self.accounts[self.current_idx]

    def rotate_next(self):
        self.current_idx = (self.current_idx + 1) % len(self.accounts)
        logger.info(f"Rotating to next Cloudflare account: {self.accounts[self.current_idx]['label']}")

def call_flux_klein_api(
    prompt: str,
    account: Dict[str, str],
    model: str = CF_MODEL,
    timeout: int = 60
) -> bytes:
    """
    Calls Cloudflare AI FLUX.2 models (Klein 4B or Klein 9B) via multipart/form-data payload
    with native 16:9 landscape dimensions (1280x720).
    Returns raw image bytes.
    """
    account_id = account["account_id"]
    token = account["token"]
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"

    headers = {
        "Authorization": f"Bearer {token}",
    }
    # Cloudflare FLUX models accept multipart/form-data width and height
    files = {
        "prompt": (None, prompt),
        "width": (None, str(IMG_WIDTH)),
        "height": (None, str(IMG_HEIGHT)),
    }

    response = requests.post(url, headers=headers, files=files, timeout=timeout)

    if response.status_code != 200:
        raise RuntimeError(f"Cloudflare API Error ({response.status_code}): {response.text[:300]}")

    content_type = response.headers.get("Content-Type", "")
    if "application/json" in content_type:
        result_json = response.json()
        img_b64 = result_json.get("result", {}).get("image")
        if not img_b64 and isinstance(result_json.get("result"), str):
            img_b64 = result_json["result"]
        if not img_b64:
            raise ValueError(f"No image data returned in Cloudflare response: {result_json}")
        return base64.b64decode(img_b64)

    return response.content

def save_normalized_png(img_bytes: bytes, output_path: Path, snap_white: bool = True) -> None:
    """Decodes raw bytes and saves a true RGB PNG.
    If snap_white is True, snaps near-white pixels (>240) to pure white using a fast C-level LUT."""
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    if snap_white:
        lut = [255 if i > 240 else i for i in range(256)] * 3
        img = img.point(lut)
    img.save(output_path, format="PNG")


def create_fallback_placeholder(output_path: Path) -> None:
    """Creates a clean white placeholder so one image flake never kills a 50-scene job."""
    try:
        # Prefer duplicating a sibling scene image to keep visual continuity.
        siblings = sorted(output_path.parent.glob("scene_*.png"))
        valid = [p for p in siblings if p != output_path and p.stat().st_size > 5000]
        if valid:
            from shutil import copyfile
            copyfile(valid[-1], output_path)
            logger.warning(f"Fallback: duplicated {valid[-1].name} -> {output_path.name}")
            return
    except Exception as e:
        logger.warning(f"Fallback duplication failed ({e}); using blank canvas.")
    Image.new("RGB", (IMG_WIDTH, IMG_HEIGHT), "white").save(output_path, "PNG")
    logger.warning(f"Fallback: blank white placeholder saved -> {output_path.name}")


def generate_single_image(
    prompt: str,
    output_path: Path,
    rotator: CloudflareImageRotator,
    max_retries: int = 5
) -> bool:
    """Generates an image with multi-account rotation and retry logic.

    Never raises on transient image failures — falls back to a placeholder
    so a single flake cannot abort a 45-50 scene render.
    """
    if output_path.exists() and output_path.stat().st_size > 5000:
        logger.info(f"[CACHE] Image already exists: {output_path.name}")
        return True

    for attempt in range(max_retries):
        account = rotator.get_current()
        try:
            t0 = time.time()
            img_bytes = call_flux_klein_api(prompt, account)
            elapsed = time.time() - t0

            save_normalized_png(img_bytes, output_path)

            logger.info(f"Generated {output_path.name} in {elapsed:.2f}s via {account['label']}")
            # Polite pause between calls
            time.sleep(0.5)
            # Rotate account after successful generation to spread load evenly
            rotator.rotate_next()
            return True

        except Exception as e:
            err_msg = str(e).lower()
            logger.warning(f"Error on {account['label']} (attempt {attempt + 1}): {e}")
            # Rotate on rate limit or error
            rotator.rotate_next()
            time.sleep(2)

    logger.error(
        f"Failed to generate image {output_path.name} after {max_retries} attempts. "
        "Using fallback placeholder instead of aborting the job."
    )
    try:
        create_fallback_placeholder(output_path)
    except Exception as e:
        logger.error(f"Fallback placeholder also failed for {output_path.name}: {e}")
        Image.new("RGB", (IMG_WIDTH, IMG_HEIGHT), "white").save(output_path, "PNG")
    return False

def generate_all_images(
    scenes: List[Dict[str, Any]],
    output_dir: Path
) -> List[Dict[str, Any]]:
    """Generates FLUX.2 images for all scenes with failure threshold protection."""
    output_dir.mkdir(parents=True, exist_ok=True)
    rotator = CloudflareImageRotator(CF_ACCOUNTS)
    logger.info(f"Generating {len(scenes)} images via FLUX.2 [klein] 4B across {len(CF_ACCOUNTS)} accounts...")

    failed_count = 0
    for i, scene in enumerate(scenes):
        scene_id = scene["scene_id"]
        img_path = output_dir / f"scene_{scene_id:02d}.png"
        prompt = scene["full_image_prompt"]

        success = generate_single_image(prompt, img_path, rotator)
        if not success:
            failed_count += 1
        scene["image_path"] = str(img_path)

        if (i + 1) % 10 == 0 or (i + 1) == len(scenes):
            logger.info(f"  Images completed: {i + 1}/{len(scenes)}")

    if failed_count > max(3, int(len(scenes) * 0.25)):
        raise RuntimeError(
            f"Excessive image generation failures: {failed_count}/{len(scenes)} scenes failed. "
            "Aborting render to prevent shipping a blank/duplicate video."
        )

    logger.info("All scene images successfully generated!")
    return scenes

def generate_thumbnail_image(
    prompt: str,
    output_path: Path,
    rotator: CloudflareImageRotator,
    model: str = CF_THUMBNAIL_MODEL,
    max_retries: int = 5
) -> bool:
    """Generates a dedicated high-CTR 16:9 thumbnail visual using FLUX.2 Klein 9B."""
    if output_path.exists() and output_path.stat().st_size > 5000:
        logger.info(f"[CACHE] Thumbnail visual already exists: {output_path.name}")
        return True

    for attempt in range(max_retries):
        account = rotator.get_current()
        try:
            t0 = time.time()
            logger.info(f"Generating thumbnail visual via {model} on {account['label']}...")
            img_bytes = call_flux_klein_api(prompt, account, model=model)
            elapsed = time.time() - t0

            save_normalized_png(img_bytes, output_path, snap_white=False)
            logger.info(f"Generated thumbnail visual {output_path.name} in {elapsed:.2f}s via {model} ({account['label']})")
            time.sleep(0.5)
            rotator.rotate_next()
            return True

        except Exception as e:
            logger.warning(f"Thumbnail visual attempt {attempt + 1}/{max_retries} failed via {account['label']}: {e}")
            rotator.rotate_next()
            time.sleep(1.5)

    logger.error("Failed to generate dedicated thumbnail visual. Using fallback placeholder.")
    create_fallback_placeholder(output_path)
    return False
