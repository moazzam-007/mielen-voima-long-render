"""
config.py
Central configuration and credentials management for Mielen Voima Long Video Engine.
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
BASE_DIR = Path(__file__).parent.resolve()
load_dotenv(BASE_DIR / ".env")

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("mielen-voima-long")

# Working Directories
JOBS_DIR = BASE_DIR / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)

# ── Cloudflare Workers AI Accounts (Rotation & Deduplication) ───────────────
CF_ACCOUNTS_RAW = [
    (os.getenv("CF_ACCOUNT_ID_1"), os.getenv("CF_API_TOKEN_1"), "CF_Account_1"),
    (os.getenv("CF_ACCOUNT_ID_2"), os.getenv("CF_API_TOKEN_2"), "CF_Account_2"),
    (os.getenv("CF_ACCOUNT_ID_3"), os.getenv("CF_API_TOKEN_3"), "CF_Account_3"),
]

CF_ACCOUNTS = []
_seen_pairs = set()
_seen_account_ids = set()
for acc_id, token, label in CF_ACCOUNTS_RAW:
    if acc_id and token:
        clean_id = acc_id.strip()
        clean_token = token.strip()
        pair = (clean_id, clean_token)
        # Quota is account-level (10k/day on Neurons), so deduplicate by
        # account ID first — two entries sharing one ID do not add capacity.
        if clean_id in _seen_account_ids:
            logger.warning(
                f"{label} shares account ID with an earlier entry — "
                "skipping duplicate (quota is account-level)."
            )
            continue
        if pair not in _seen_pairs:
            _seen_pairs.add(pair)
            _seen_account_ids.add(clean_id)
            CF_ACCOUNTS.append({
                "account_id": clean_id,
                "token": clean_token,
                "label": label
            })

if not CF_ACCOUNTS:
    logger.warning("No Cloudflare credentials found in environment variables!")

CF_MODEL = "@cf/black-forest-labs/flux-2-klein-4b"

# ── LLM Credentials & Cascading Fallback Chain (Google AI Studio + OpenRouter) ─
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()

GEMINI_FALLBACK_CHAIN = [
    {
        "model": "gemini-3.5-flash-lite",
        "provider": "google",
        "retries": 2,
        "pause": 15,
        "thinking_level": "LOW",
        "max_output_tokens": 32768,
    },
    {
        "model": "gemini-3-flash-preview",
        "provider": "google",
        "retries": 2,
        "pause": 15,
        "max_output_tokens": 32768,
    },
    {
        "model": "nvidia/nemotron-3-super-120b-a12b:free",
        "provider": "openrouter",
        "retries": 2,
        "pause": 5,
        "max_output_tokens": 32768,
    },
    {
        "model": "nvidia/nemotron-3-ultra-550b-a55b:free",
        "provider": "openrouter",
        "retries": 2,
        "pause": 5,
        "max_output_tokens": 32768,
    },
    {
        "model": "nvidia/nemotron-3.5-lightning:free",
        "provider": "openrouter",
        "retries": 2,
        "pause": 5,
        "max_output_tokens": 32768,
    },
    {
        "model": "gemma-4-26b-a4b-it",
        "provider": "google",
        "retries": 2,
        "pause": 10,
        "max_output_tokens": 32768,
    },
    {
        "model": "gemini-3.1-flash-lite",
        "provider": "google",
        "retries": 2,
        "pause": 15,
        "max_output_tokens": 32768,
    },
]

# Allow overriding the primary model via GEMINI_PRIMARY_MODEL while maintaining the fallback chain
GEMINI_PRIMARY_MODEL = os.getenv("GEMINI_PRIMARY_MODEL", "").strip()
if GEMINI_PRIMARY_MODEL:
    existing_tier = next((tier for tier in GEMINI_FALLBACK_CHAIN if tier["model"] == GEMINI_PRIMARY_MODEL), None)
    if existing_tier:
        GEMINI_FALLBACK_CHAIN = [tier for tier in GEMINI_FALLBACK_CHAIN if tier["model"] != GEMINI_PRIMARY_MODEL]
        GEMINI_FALLBACK_CHAIN.insert(0, existing_tier)
    else:
        provider = "openrouter" if "/" in GEMINI_PRIMARY_MODEL else "google"
        GEMINI_FALLBACK_CHAIN.insert(0, {
            "model": GEMINI_PRIMARY_MODEL,
            "provider": provider,
            "retries": 2,
            "pause": 15,
            "max_output_tokens": 16384,
        })

GEMINI_MODEL = GEMINI_FALLBACK_CHAIN[0]["model"]

# ── Security & Web Service ──────────────────────────────────────────────────
API_SECRET_KEY = os.getenv("API_SECRET_KEY", "").strip()
if not API_SECRET_KEY:
    logger.warning(
        "API_SECRET_KEY is not set in environment variables! "
        "Set API_SECRET_KEY in production to enforce X-API-Key authentication."
    )
PORT = int(os.getenv("PORT", "10000"))

# ── Voice & Audio Settings ──────────────────────────────────────────────────
VOICE_DEFAULT = "fi-FI-HarriNeural"
VOICE_RATE = "-2%"
AUDIO_TRAILING_GAP_MS = 100       # Clean gap between spoken lines
AUDIO_MICRO_FADE_OUT_MS = 15      # Anti-pop fade out

# ── Prompt Assembly Constants (Boilerplate Injected via Code) ───────────────
STYLE_PREFIX = (
    "Minimalist flat 2D black ink doodle on a pure white (#FFFFFF) background, "
    "thick clean outlines, lots of empty space. Character: a bare stick figure with a "
    "round white head, two black dot eyes, simple mouth line, thin black line limbs."
)

STYLE_SUFFIX = (
    "all subjects placed in upper 75% of frame, bottom quarter left completely empty "
    "white canvas for subtitles, clean black doodle line art, flat solid fills, family friendly."
)

# ── Video & Subtitle Visual Standards ────────────────────────────────────────
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
VIDEO_FPS = 30

# Subtitle Styling: Pure Solid Black, ZERO White Outline, Centered Bottom
SUBTITLE_STYLE = {
    "Fontname": "Arial",
    "Fontsize": "50",
    "PrimaryColour": "&H00000000",   # Solid Black (ASS hex: &HAABBGGRR)
    "OutlineColour": "&H00000000",   # No Outline color
    "BackColour": "&H00000000",
    "Bold": "1",
    "Italic": "0",
    "Outline": "0",                  # STRICT: Outline = 0
    "Shadow": "0",                   # STRICT: Shadow = 0
    "Alignment": "2",                # Centered Bottom
    "MarginV": "50",                 # Bottom Margin
    "BorderStyle": "1"
}

# Thumbnail Branding Colors
THUMB_BG = (255, 255, 255)           # Pure White #FFFFFF
THUMB_HIGHLIGHT_BOX = (251, 191, 36) # Amber Yellow #FBBF24
THUMB_TEXT_BLACK = (0, 0, 0)         # Pure Black
