"""
modules/gemini_engine.py
Gemini 3.8 Flash Engine: Chunks full Finnish script into scenes,
generates 30-50 words positive scene descriptions, and assembles final FLUX.2 prompts.
"""

import json
import re
import time
import requests
from typing import List, Dict, Any

from config import (
    logger,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    STYLE_PREFIX,
    STYLE_SUFFIX
)

SYSTEM_PROMPT = """You are the Lead Visual Director for the Finnish psychology YouTube channel MIELEN VOIMA (@Mielen_Voima).

Your ONLY task is to read the provided Finnish script, divide it into chronological scenes (target 40-50 scenes, each 10-18 words spoken chunk), and write a lean, highly visual scene prompt (30 to 50 words) for each scene.

CRITICAL: Style prefix, canvas background, character boilerplate, and subtitle safe-area suffix are attached automatically by the rendering code. Do NOT write them. Write ONLY the unique scene description.

═══════════════════════════════════════════════════════════════
1. VISUAL IDENTITY & STRICT SCENE RULES
═══════════════════════════════════════════════════════════════
1. FIGURE LIMIT:
   - Exactly ONE bare stick figure per scene (max 2 figures ONLY if the line describes an interaction between two people). Never draw crowds.

2. OBJECT LIMIT (MAX 1 TO 2 CONCRETE OBJECTS):
   - Include maximum 1 to 2 simple, physical doodle objects per scene (e.g. magnifying glass, balance scale, puzzle cube, hourglass, ladder, box).
   - Each object must have a clear shape and screen position (left, right, center, above, below).

3. ONE CLEAR ACTION VERB:
   - Use simple, active physical verbs: stands, sits, holds, points, reaches, carries, leans.

4. ACCENT COLOR (MAX ONE PER SCENE):
   - Props only, never on the stick figure or background. Choose the single best fit:
     * Amber Yellow (#FBBF24): Wisdom, lightbulb, insight, golden gift.
     * Crimson Red (#EF4444): Stress, overthinking knot, obstacle, warning.
     * Calming Teal (#06B6D4): Clarity, peace, boundary shield, detachment.
     * Emerald Green (#10B981): Growth, checkmark, balance, forward step.

5. ZERO TEXT IN IMAGE (STRICT):
   - NEVER include words, letters, numbers, labels, signs, or text in the scene prompt.
   - All keywords and numbered badges are overlaid programmatically in code.

6. POSITIVE PHRASING ONLY (NO NEGATIVE WORDS):
   - Never use "no", "not", "without", "zero", "never" in the scene prompt. Describe what IS in the scene, not what isn't.
   - BANNED CONCEPTS: mirrors, reflections, transparency, water, night skies, stars, shading, shadows, 3D shapes.

7. COMPOSITION DIVERSITY:
   - Cycle dynamically through these compositions so adjacent scenes never repeat the same angle:
     * centered | left_third | right_third | close_up_object | wide_small_figure | top_down

═══════════════════════════════════════════════════════════════
2. PROMPT LENGTH REQUIREMENT
═══════════════════════════════════════════════════════════════
- Each 'scene_prompt' MUST be strictly between 30 to 50 words in length.
- Concise, positive, physical scene description specifying the figure's position, pose, and prop details.

═══════════════════════════════════════════════════════════════
3. OUTPUT FORMAT (STRICT JSON ONLY)
═══════════════════════════════════════════════════════════════
Output a strict JSON array under the "scenes" key:

{
  "scenes": [
    {
      "scene_id": 1,
      "spoken_chunk": "Exact Finnish sentence or chunk from the script",
      "keyword": "SINGLE_FINNISH_KEYWORD",
      "concept": "High intelligence seen as a gift",
      "concrete_object": "A large gift box with ribbon",
      "composition": "centered",
      "scene_prompt": "The stick figure stands centered with a proud posture, holding up a large doodle gift box with an amber yellow (#FBBF24) ribbon on top. Short radiant doodle ray lines expand outward from the box."
    }
  ]
}
"""

def sanitize_scene_prompt(prompt: str) -> str:
    """Lightweight post-filter: strips accidental negative words and text badges.

    The system prompt already forbids negatives and in-image text, but this
    guards against Gemini slipping in e.g. 'no shadows', 'without text', or
    'with letter badges' before the prompt reaches FLUX.
    """
    if not prompt:
        return prompt
    cleaned = prompt
    # Remove text-badge phrases ("with text", "showing letters", "with number labels", ...)
    # Loop until stable to catch stacked badges like "with text labels".
    phrase_pat = (
        r"\b(with|without|containing|showing|featuring|holding|reading)\b[^.,;]{0,40}?"
        r"\b(words?|letters?|numbers?|labels?|signs?|texts?|badges?|captions?)\b"
        r"(?:\s+\b(?:words?|letters?|numbers?|labels?|signs?|texts?|badges?|captions?)\b)*"
    )
    prev = None
    while prev != cleaned:
        prev = cleaned
        cleaned = re.sub(phrase_pat, "", cleaned, flags=re.IGNORECASE)
    # Strip any leftover standalone badge words (they imply in-image text, which is banned).
    cleaned = re.sub(
        r"\b(words?|letters?|numbers?|labels?|signs?|texts?|badges?|captions?)\b",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Strip standalone negative words (describe what IS present, not what isn't).
    cleaned = re.sub(
        r"\b(no|not|without|zero|never|none|nobody|nothing|neither|nor)\b",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Collapse whitespace / stray punctuation left behind.
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    cleaned = re.sub(r"\s+([.,;])", r"\1", cleaned)
    return cleaned


def split_and_generate_prompts(script_text: str, max_retries: int = 3) -> List[Dict[str, Any]]:
    """
    Calls Gemini 3.8 Flash to chunk Finnish script into scenes and generate scene prompts.
    Returns list of scene dicts with assembled full FLUX.2 image prompts.
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not configured!")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    headers = {
        "x-goog-api-key": GEMINI_API_KEY,
        "Content-Type": "application/json",
    }

    user_message = (
        f"Tässä on videon TÄYSI suomenkielinen käsikirjoitus. "
        f"Jaa se kronologisesti 40-50 luonnolliseen kohtaukseen ja luo jokaiselle kohtaukselle "
        f"tarkka 30-50 sanan kuvaus ohjeiden mukaisesti JSON-muodossa.\n\n"
        f"=== KÄSIKIRJOITUS ===\n{script_text.strip()}\n=== KÄSIKIRJOITUKSEN LOPPU ==="
    )

    payload = {
        "system_instruction": {
            "parts": [{"text": SYSTEM_PROMPT}]
        },
        "contents": [
            {
                "parts": [{"text": user_message}]
            }
        ],
        "generationConfig": {
            "response_mime_type": "application/json",
            "maxOutputTokens": 8192
        }
    }

    logger.info("Calling Gemini 3.8 Flash for scene chunking and prompt generation...")
    parsed = None

    for attempt in range(max_retries):
        t0 = time.time()
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=120)
            elapsed = time.time() - t0
            logger.info(f"Gemini Attempt {attempt + 1}: Status {r.status_code} in {elapsed:.2f}s")

            if r.status_code == 200:
                try:
                    data = r.json()
                except Exception as e:
                    logger.warning(f"Gemini returned non-JSON body (attempt {attempt + 1}): {e}")
                    time.sleep(2)
                    continue
                candidates = data.get("candidates")
                if not candidates:
                    logger.warning(
                        f"Gemini returned no candidates (attempt {attempt + 1}): "
                        f"{str(data)[:300]} — possibly safety-blocked. Retrying..."
                    )
                    time.sleep(2)
                    continue
                finish_reason = candidates[0].get("finishReason", "")
                if finish_reason and finish_reason not in ("STOP", ""):
                    logger.warning(
                        f"Gemini finishReason={finish_reason} (attempt {attempt + 1}). Retrying..."
                    )
                    time.sleep(2)
                    continue
                try:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if not parts or "text" not in parts[0]:
                        logger.warning(f"Gemini response missing text parts (attempt {attempt + 1}). Retrying...")
                        time.sleep(2)
                        continue
                    raw_text = parts[0]["text"].strip()
                    # Strip markdown fences if the model wrapped JSON in ```json ... ```
                    if raw_text.startswith("```"):
                        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
                        raw_text = re.sub(r"\s*```$", "", raw_text)
                    parsed = json.loads(raw_text)
                    if not parsed.get("scenes"):
                        logger.warning(f"Gemini returned empty scenes list (attempt {attempt + 1}). Retrying...")
                        parsed = None
                        time.sleep(2)
                        continue
                    break
                except (json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
                    logger.warning(f"Gemini JSON parse failed (attempt {attempt + 1}): {e}. Retrying...")
                    parsed = None
                    time.sleep(2)
                    continue
            elif r.status_code == 503:
                logger.warning("Gemini 503 (High Demand). Retrying in 4 seconds...")
                time.sleep(4)
            else:
                logger.error(f"Gemini API error {r.status_code}: {r.text[:300]}")
                time.sleep(2)
        except Exception as e:
            logger.error(f"Gemini connection error: {e}")
            time.sleep(3)

    if not parsed:
        raise RuntimeError("Failed to obtain response from Gemini 3.8 Flash after retries.")

    raw_scenes = parsed.get("scenes", [])

    if not raw_scenes:
        raise ValueError("Gemini returned empty scenes list!")

    logger.info(f"Gemini successfully chunked script into {len(raw_scenes)} scenes.")

    # Assemble final FLUX.2 prompts using code boilerplate constants
    processed_scenes = []
    for s in raw_scenes:
        scene_prompt = sanitize_scene_prompt(s.get("scene_prompt", "").strip())
        # Combine: STYLE_PREFIX + scene_prompt + STYLE_SUFFIX
        full_image_prompt = f"{STYLE_PREFIX} {scene_prompt} {STYLE_SUFFIX}"

        processed_scenes.append({
            "scene_id": s.get("scene_id"),
            "spoken_chunk": s.get("spoken_chunk", "").strip(),
            "keyword": s.get("keyword", "").upper().strip(),
            "concept": s.get("concept", ""),
            "concrete_object": s.get("concrete_object", ""),
            "composition": s.get("composition", "centered"),
            "scene_prompt": scene_prompt,
            "full_image_prompt": full_image_prompt,
        })

    return processed_scenes
