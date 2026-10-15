"""
modules/gemini_engine.py
Gemini Cascading Fallback Engine: Chunks full Finnish script into scenes,
generates 25-35 words positive scene descriptions, and assembles final FLUX.2 prompts.
"""

import json
import re
import time
import requests
from typing import List, Dict, Any, Optional

from config import (
    logger,
    GEMINI_API_KEY,
    OPENROUTER_API_KEY,
    GEMINI_FALLBACK_CHAIN,
    GEMINI_MODEL,
    STYLE_PREFIX,
    STYLE_SUFFIX
)

SYSTEM_PROMPT = """You are the Lead Visual Director for the Finnish psychology YouTube channel MIELEN VOIMA (@Mielen_Voima).

Your ONLY task is to read the provided Finnish script, divide it into chronological scenes (target 35-45 scenes, each 10-18 words spoken chunk), and write a lean, highly visual scene prompt strictly in English for each scene (target 30-45 words).

CRITICAL: Style prefix (canvas background, character identity) and safe-area suffix are attached automatically by the rendering code. Do NOT write boilerplate styles. Write ONLY the unique physical scene action, props, and psychological visual metaphors.

═══════════════════════════════════════════════════════════════
1. VISUAL IDENTITY & COMPOSITION RULES
═══════════════════════════════════════════════════════════════
1. LANGUAGE:
   - "scene_prompt" must ALWAYS be written in ENGLISH so the image generation model understands it accurately.
   - "spoken_chunk" and "keyword" remain in FINNISH.

2. PURE WHITE CANVAS & STICKMAN IDENTITY:
   - Background is always pure white (#FFFFFF).
   - Character is a minimalist hand-drawn 2D whiteboard stickman with a round white head, thin black outline, small dot eyes, simple expressive mouth, and thin black-line limbs.

3. FREE COLOR CREATIVITY ON SUPPORTING ELEMENTS:
   - Stickman is always black outline & white fill. Background is always pure white.
   - For all supporting objects, props, environmental doodle elements, and psychological metaphors: You have FULL CREATIVE FREEDOM to use any flat colors or accent combinations without restriction (e.g. amber yellow, crimson red, emerald green, warm amber, cyan, navy, pastel tones).
   - Keep all colors flat 2D cartoon style (no 3D shading, no photorealistic lighting, no gradients).

4. CONCRETE PSYCHOLOGICAL METAPHORS & LAYERED STORYTELLING:
   - Turn abstract mental concepts into concrete physical visual metaphors with rich storytelling depth.
   - Combine 2 to 3 evocative symbols in emotional scenes: floating thought bubbles with tiny doodle scribbles inside, tangled black wires trailing down to the floor, fragmented floating clocks, faint shadowy silhouettes in soft gray, or a focused overhead spotlight beam.
   - Ground the figure on simple doodle furniture when depicting deep psychological states (e.g. sitting on the edge of a bed holding head in stress, hunched over a wooden desk with papers, leaning against a closed door, standing at the edge of a precipice).
   - Position props clearly in the 16:9 widescreen frame (left, right, center, overhead).

5. EXPRESSIVE BODY LANGUAGE & ACTION:
   - Use active, physical verbs with clear emotion: sits on the edge of a bed holding head in exhaustion, stands proudly, walks forward through crowd, balances cautiously, reaches upward, pulls a heavy rope, inspects with curiosity.

6. ZERO TEXT IN IMAGE (STRICT):
   - NEVER include words, letters, numbers, signs, captions, or labels in the scene prompt.
   - Finnish keywords are rendered programmatically by the video engine.

7. POSITIVE PHRASING ONLY (NO NEGATIVE WORDS):
   - Always describe what IS present in the scene. Never use negative words like "no", "not", "without", "zero", "never".
   - Avoid photorealism, mirrors, water reflections, night skies, stars, and 3D rendering.

8. COMPOSITION DIVERSITY (16:9 WIDE):
   - Start each scene prompt with its composition framing:
     * centered | left_third | right_third | wide_angle | close_up_props

═══════════════════════════════════════════════════════════════
2. REFERENCE EXAMPLES (LEARN FROM THESE HIGH-QUALITY SCENES)
═══════════════════════════════════════════════════════════════
Study these 4 reference examples for tone, depth, and visual storytelling:

Example 1 (The Psychology of Overthinking):
"centered: The stickman sits on the edge of a simple bed holding his head in stress under a focused overhead spotlight beam. Around him float thought bubbles with tiny doodle scribbles, tangled black wires trailing to the floor, fragmented clocks, and faint soft gray silhouettes on the clean white canvas."

Example 2 (The Illusion of Control / Manipulation):
"left_third: The stickman stands confidently on the left holding an oversized wooden marionette control bar. Thin black strings extend down to a tiny duplicate stick figure kneeling on the right floor, mirroring his exact posture."

Example 3 (Procrastination & Overwhelm):
"right_third: The stickman stands on the right wearing a small travel backpack, looking nervously up at an impossibly steep mountain made of giant stacked books, oversized alarm clocks, and checklist pads towering over him."

Example 4 (Loneliness / Inner Focus in a Fast World):
"centered: The stickman walks forward through a minimalist street carrying a warm glowing yellow lantern that illuminates his immediate steps, while faint soft gray silhouettes of busy pedestrians walk past in opposite directions."

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
      "concrete_object": "A large gift box with colorful ribbon",
      "composition": "centered",
      "scene_prompt": "centered: The stickman stands with an upright posture, holding up a large gift box tied with a bright yellow ribbon. Radiant doodle rays expand outward from the box into the clean white space."
    }
  ]
}
"""

THUMBNAIL_SYSTEM_PROMPT = """You are the World-Class Creative Art Director for the Finnish psychology YouTube channel MIELEN VOIMA (@Mielen_Voima).

Your task is to analyze the provided video title and script, and create an intensely compelling, hyper-detailed, high-CTR YouTube Thumbnail Visual Prompt for the FLUX.2 Klein 9B image generation model.

═══════════════════════════════════════════════════════════════
THUMBNAIL DESIGN & PROMPT SPECIFICATIONS
═══════════════════════════════════════════════════════════════
1. ARTISTIC STYLE:
   - High-end 2D psychological illustration with semi-realistic depth, expressive painterly textures, and tangible forms.
   - Conceptual surrealism and modern psychological abstract art (reminiscent of prestige editorial psychology magazine covers).
   - Dramatic cinematic lighting, volumetric atmosphere, focused overhead spotlighting, deep evocative shadows, and luminous focal glow.

2. VISUAL HOOK (PURELY VISUAL, ZERO TEXT):
   - The hook must be 100% VISUAL — an impossible, surreal, or paradoxical psychological metaphor that creates an irresistible curiosity gap.
   - Ideas for visual curiosity hooks:
     * A human figure whose silhouette reveals an intricate glowing labyrinth, fractured architectural mindscape, or storm inside.
     * Giant glowing neural strings or marionette threads tying multiple contrasting versions of the self.
     * A colossal glowing lightbulb containing a surreal storm, puzzle pieces, or hourglass floating in deep space.
     * A solitary figure standing before an immense, glowing split doorway showing two conflicting psychological destinies.
     * An intricate surreal clock melting or shattering into floating crystalline memory fragments.

3. STRICT RULE: ABSOLUTELY ZERO TEXT / WORDS:
   - NEVER include words, typography, letters, numbers, signs, logos, or captions in the prompt.
   - The visual storytelling alone must captivate the viewer.

4. COMPOSITION & COLOR PALETTE:
   - Native 16:9 widescreen composition with the primary focal subject strictly centered so it is never cropped. Bold, high-contrast silhouette that pops even at tiny mobile screen sizes (170px).
   - High-contrast color grading: rich deep charcoals, moody indigos, accented by piercing luminous highlights (radiant amber yellow, electric cyan, or subtle crimson tension).

5. PROMPT DEPTH & LENGTH:
   - Write a concise, potent, highly detailed prompt strictly between 120 and 180 words (preventing FLUX 512-token truncation).
   - Focus the first 2 sentences on the central subject, visual hook, and dramatic lighting.

═══════════════════════════════════════════════════════════════
OUTPUT FORMAT (STRICT JSON ONLY)
═══════════════════════════════════════════════════════════════
Return a valid JSON object:
{
  "concept": "Core psychological theme and visual metaphor summary",
  "visual_hook": "Description of the visual curiosity gap",
  "thumbnail_prompt": "Concise, hyper-detailed English prompt (120-180 words) ready for FLUX.2 Klein 9B..."
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


def split_and_generate_prompts(
    script_text: str,
    fallback_chain: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    """
    Calls Gemini cascading fallback chain to chunk Finnish script into scenes and generate scene prompts.
    Tiers through models on 503, 429, timeouts, token limits, or malformed responses.
    Returns list of scene dicts with assembled full FLUX.2 image prompts.
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not configured!")

    if fallback_chain is None:
        fallback_chain = GEMINI_FALLBACK_CHAIN

    if not fallback_chain:
        raise ValueError("GEMINI_FALLBACK_CHAIN is empty!")

    user_message = (
        f"Tässä on videon TÄYSI suomenkielinen käsikirjoitus. "
        f"Jaa se kronologisesti 35-45 luonnolliseen kohtaukseen ja luo jokaiselle kohtaukselle "
        f"tiivis, tarkka 30-45 sanan kuvaus (scene_prompt englanniksi) ohjeiden mukaisesti JSON-muodossa.\n\n"
        f"=== KÄSIKIRJOITUS ===\n{script_text.strip()}\n=== KÄSIKIRJOITUKSEN LOPPU ==="
    )

    logger.info(
        f"Starting multi-provider scene chunking & prompt generation across {len(fallback_chain)} fallback tiers "
        f"(Primary: {fallback_chain[0]['model']})..."
    )

    parsed = None

    for tier_idx, tier in enumerate(fallback_chain):
        model = tier.get("model", "")
        provider = tier.get("provider", "openrouter" if "/" in model else "google")
        max_retries = tier.get("retries", 2)
        pause = tier.get("pause", 15)
        max_output_tokens = tier.get("max_output_tokens", 16384)
        thinking_level = tier.get("thinking_level")

        if provider == "openrouter" and not OPENROUTER_API_KEY:
            logger.warning(
                f"[Tier {tier_idx + 1}/{len(fallback_chain)}] Skipping OpenRouter model {model} "
                "because OPENROUTER_API_KEY is not configured."
            )
            continue

        logger.info(
            f"[Tier {tier_idx + 1}/{len(fallback_chain)}] Engaging {provider.upper()} model {model} "
            f"(max retries: {max_retries}, pause: {pause}s)..."
        )

        for attempt in range(max_retries):
            t0 = time.time()
            try:
                if provider == "openrouter":
                    url = "https://openrouter.ai/api/v1/chat/completions"
                    headers = {
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "HTTP-Referer": "https://mielenvoima.youtube.internal",
                        "X-Title": "Mielen Voima Production Engine",
                        "Content-Type": "application/json"
                    }
                    payload = {
                        "model": model,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_message}
                        ],
                        "response_format": {"type": "json_object"},
                        "reasoning": {
                            "effort": "low",
                            "exclude": True
                        },
                        "plugins": [{"id": "response-healing"}],
                        "temperature": 0.3,
                        "max_tokens": max_output_tokens
                    }
                else:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                    headers = {
                        "x-goog-api-key": GEMINI_API_KEY,
                        "Content-Type": "application/json",
                    }
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
                            "maxOutputTokens": max_output_tokens
                        }
                    }
                    if thinking_level:
                        payload["generationConfig"]["thinkingConfig"] = {"thinkingLevel": thinking_level}

                timeout_sec = 180 if provider == "openrouter" else 90
                r = requests.post(url, headers=headers, json=payload, timeout=timeout_sec)
                elapsed = time.time() - t0
                logger.info(f"Model {model} Attempt {attempt + 1}/{max_retries}: Status {r.status_code} in {elapsed:.2f}s")

                if r.status_code == 200:
                    try:
                        data = r.json()
                    except Exception as e:
                        logger.warning(
                            f"[WARNING] Model {model} attempt {attempt + 1}/{max_retries} failed with JSONDecodeError: {e}. "
                            f"Pausing {pause}s before retry..."
                        )
                        if attempt < max_retries - 1:
                            time.sleep(pause)
                        continue

                    if provider == "openrouter":
                        choices = data.get("choices")
                        if not choices:
                            logger.warning(f"[WARNING] OpenRouter model {model} returned no choices: {data}")
                            if attempt < max_retries - 1:
                                time.sleep(pause)
                            continue
                        msg = choices[0].get("message", {})
                        content_val = msg.get("content")
                        reasoning_val = msg.get("reasoning")
                        if content_val is not None and str(content_val).strip():
                            raw_text = str(content_val).strip()
                        elif reasoning_val is not None and str(reasoning_val).strip():
                            raw_text = str(reasoning_val).strip()
                        else:
                            raw_text = ""
                    else:
                        candidates = data.get("candidates")
                        if not candidates:
                            logger.warning(
                                f"[WARNING] Model {model} attempt {attempt + 1}/{max_retries} returned no candidates: {str(data)[:300]} "
                                f"(safety blocked or empty). Pausing {pause}s before retry..."
                            )
                            if attempt < max_retries - 1:
                                time.sleep(pause)
                            continue

                        candidate = candidates[0]
                        finish_reason = candidate.get("finishReason", "")
                        if finish_reason == "MAX_TOKENS":
                            logger.warning(
                                f"[WARNING] Model {model} attempt {attempt + 1}/{max_retries} failed with finishReason: MAX_TOKENS "
                                f"(output token limit exceeded). Pausing {pause}s before retry..."
                            )
                            if attempt < max_retries - 1:
                                time.sleep(pause)
                            continue
                        elif finish_reason and finish_reason not in ("STOP", ""):
                            logger.warning(
                                f"[WARNING] Model {model} attempt {attempt + 1}/{max_retries} failed with finishReason: {finish_reason}. "
                                f"Pausing {pause}s before retry..."
                            )
                            if attempt < max_retries - 1:
                                time.sleep(pause)
                            continue

                        parts = candidate.get("content", {}).get("parts", [])
                        raw_text = "".join(p.get("text", "") for p in parts if "text" in p).strip()

                    if not raw_text:
                        logger.warning(
                            f"[WARNING] Model {model} attempt {attempt + 1}/{max_retries} returned empty text content. "
                            f"Pausing {pause}s before retry..."
                        )
                        if attempt < max_retries - 1:
                            time.sleep(pause)
                        continue

                    if raw_text.startswith("```"):
                        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
                        raw_text = re.sub(r"\s*```$", "", raw_text)

                    try:
                        parsed_json = json.loads(raw_text)
                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"[WARNING] Model {model} attempt {attempt + 1}/{max_retries} failed with JSONDecodeError / Malformed output: {e}. "
                            f"Pausing {pause}s before retry..."
                        )
                        if attempt < max_retries - 1:
                            time.sleep(pause)
                        continue

                    raw_scenes = parsed_json.get("scenes") if isinstance(parsed_json, dict) else None
                    if not raw_scenes or not isinstance(raw_scenes, list):
                        logger.warning(
                            f"[WARNING] Model {model} attempt {attempt + 1}/{max_retries} returned empty or invalid scenes list. "
                            f"Pausing {pause}s before retry..."
                        )
                        if attempt < max_retries - 1:
                            time.sleep(pause)
                        continue

                    # Successful response and valid JSON parsing with non-empty scenes
                    logger.info(
                        f"Model {model} succeeded on attempt {attempt + 1}/{max_retries} "
                        f"({len(raw_scenes)} scenes generated in {elapsed:.2f}s)."
                    )
                    parsed = parsed_json
                    break

                elif r.status_code == 503:
                    logger.warning(
                        f"[WARNING] Model {model} attempt {attempt + 1}/{max_retries} failed with HTTP 503 (High Demand / Service Unavailable). "
                        f"Pausing {pause}s before retry..."
                    )
                    if attempt < max_retries - 1:
                        time.sleep(pause)
                    continue

                elif r.status_code == 429:
                    logger.warning(
                        f"[WARNING] Model {model} attempt {attempt + 1}/{max_retries} failed with HTTP 429 (Rate Limit). "
                        f"Pausing {pause}s before retry..."
                    )
                    if attempt < max_retries - 1:
                        time.sleep(pause)
                    continue

                else:
                    logger.warning(
                        f"[WARNING] Model {model} attempt {attempt + 1}/{max_retries} failed with HTTP {r.status_code}: {r.text[:300]}. "
                        f"Pausing {pause}s before retry..."
                    )
                    if attempt < max_retries - 1:
                        time.sleep(pause)
                    continue

            except requests.exceptions.Timeout as e:
                logger.warning(
                    f"[WARNING] Model {model} attempt {attempt + 1}/{max_retries} failed with Read timed out (timeout=65s): {e}. "
                    f"Pausing {pause}s before retry..."
                )
                if attempt < max_retries - 1:
                    time.sleep(pause)
                continue
            except requests.exceptions.RequestException as e:
                logger.warning(
                    f"[WARNING] Model {model} attempt {attempt + 1}/{max_retries} failed with connection error: {e}. "
                    f"Pausing {pause}s before retry..."
                )
                if attempt < max_retries - 1:
                    time.sleep(pause)
                continue
            except Exception as e:
                logger.warning(
                    f"[WARNING] Model {model} attempt {attempt + 1}/{max_retries} failed with unexpected error: {e}. "
                    f"Pausing {pause}s before retry..."
                )
                if attempt < max_retries - 1:
                    time.sleep(pause)
                continue

        if parsed:
            break

        next_model = (
            fallback_chain[tier_idx + 1]["model"]
            if tier_idx + 1 < len(fallback_chain)
            else "NONE (end of chain)"
        )
        logger.warning(
            f"[WARNING] All retries exhausted for {model}. "
            f"Falling back to next tier: {next_model}..."
        )

    if not parsed:
        raise RuntimeError("All Gemini fallback tiers exhausted")

    raw_scenes = parsed.get("scenes", [])
    if not raw_scenes:
        raise ValueError("Gemini returned empty scenes list!")

    logger.info(f"Gemini successfully chunked script into {len(raw_scenes)} scenes.")

    # Assemble final FLUX.2 prompts using code boilerplate constants
    processed_scenes = []
    for s in raw_scenes:
        chunk = s.get("spoken_chunk", "").strip()
        # Prevent Edge-TTS crash on empty or punctuation-only chunks
        if not re.search(r"\w", chunk):
            logger.warning(f"Skipping empty or punctuation-only spoken chunk: '{chunk}'")
            continue

        scene_prompt = sanitize_scene_prompt(s.get("scene_prompt", "").strip())
        # Combine: STYLE_PREFIX + scene_prompt + STYLE_SUFFIX
        full_image_prompt = f"{STYLE_PREFIX} {scene_prompt} {STYLE_SUFFIX}"

        processed_scenes.append({
            "scene_id": len(processed_scenes) + 1,  # Strictly unique sequential integer (prevents string & collision bugs)
            "spoken_chunk": chunk,
            "keyword": s.get("keyword", "").upper().strip(),
            "concept": s.get("concept", ""),
            "concrete_object": s.get("concrete_object", ""),
            "composition": s.get("composition", "centered"),
            "scene_prompt": scene_prompt,
            "full_image_prompt": full_image_prompt,
        })

    return processed_scenes


def generate_thumbnail_prompt(
    title: str,
    script_text: str,
    fallback_chain: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Dedicated Gemini API call to craft an intensely compelling, hyper-detailed
    psychological abstract art thumbnail prompt (semi-realistic 2D, zero text, strong visual hook)
    tailored specifically for FLUX.2 Klein 9B.
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not configured!")

    if fallback_chain is None:
        fallback_chain = GEMINI_FALLBACK_CHAIN

    # Focus on the first 3000 characters of the script to capture the hook & central thesis
    script_summary = script_text[:3000].strip()

    user_message = (
        f"Luo äärimmäisen kiehtova, psykologinen YouTube-pikkukuvan (thumbnail) visuaalinen kuvaus "
        f"seuraavalle videolle. Kuvan tulee olla semi-realistinen 2D-psykologinen abstrakti taideteos, "
        f"jossa on vahva visuaalinen koukku, mutta EI LAINKAAN TEKSTIÄ.\n\n"
        f"=== VIDEON OTSIKKO ===\n{title.strip()}\n\n"
        f"=== KÄSIKIRJOITUKSEN YDIN ===\n{script_summary}\n\n"
        f"Kirjoita syvä, hyper-yksityiskohtainen ja vaikuttava 'thumbnail_prompt' englanniksi FLUX.2 Klein 9B -mallille JSON-muodossa."
    )

    logger.info(f"Generating dedicated AI thumbnail visual prompt with primary model {fallback_chain[0]['model']}...")

    for tier_idx, tier in enumerate(fallback_chain):
        model = tier.get("model", "")
        provider = tier.get("provider", "openrouter" if "/" in model else "google")
        max_retries = tier.get("retries", 2)
        pause = tier.get("pause", 10)
        max_output_tokens = 4096
        thinking_level = tier.get("thinking_level")

        if provider == "openrouter" and not OPENROUTER_API_KEY:
            continue

        for attempt in range(max_retries):
            try:
                if provider == "openrouter":
                    url = "https://openrouter.ai/api/v1/chat/completions"
                    headers = {
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "HTTP-Referer": "https://mielenvoima.youtube.internal",
                        "X-Title": "Mielen Voima Production Engine",
                        "Content-Type": "application/json"
                    }
                    payload = {
                        "model": model,
                        "messages": [
                            {"role": "system", "content": THUMBNAIL_SYSTEM_PROMPT},
                            {"role": "user", "content": user_message}
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.4,
                        "max_tokens": max_output_tokens
                    }
                else:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                    headers = {
                        "x-goog-api-key": GEMINI_API_KEY,
                        "Content-Type": "application/json",
                    }
                    payload = {
                        "system_instruction": {
                            "parts": [{"text": THUMBNAIL_SYSTEM_PROMPT}]
                        },
                        "contents": [
                            {
                                "parts": [{"text": user_message}]
                            }
                        ],
                        "generationConfig": {
                            "response_mime_type": "application/json",
                            "maxOutputTokens": max_output_tokens
                        }
                    }
                    if thinking_level:
                        payload["generationConfig"]["thinkingConfig"] = {"thinkingLevel": thinking_level}

                timeout_sec = 60
                r = requests.post(url, headers=headers, json=payload, timeout=timeout_sec)
                if r.status_code != 200:
                    logger.warning(
                        f"Thumbnail prompt model {model} attempt {attempt + 1}/{max_retries} "
                        f"failed with HTTP {r.status_code}: {r.text[:200]}"
                    )
                    time.sleep(pause)
                    continue

                resp_json = r.json()
                raw_text = ""
                if provider == "openrouter":
                    raw_text = resp_json["choices"][0]["message"]["content"]
                else:
                    candidates = resp_json.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        raw_text = "".join(p.get("text", "") for p in parts)

                # Extract JSON object
                m = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
                if m:
                    data = json.loads(m.group(0))
                    prompt = data.get("thumbnail_prompt") or data.get("prompt")
                    if prompt:
                        cleaned = sanitize_scene_prompt(prompt.strip())
                        logger.info(f"Successfully generated AI thumbnail prompt ({len(cleaned.split())} words).")
                        return cleaned
            except Exception as e:
                logger.warning(f"Thumbnail prompt attempt {attempt + 1}/{max_retries} with {model} failed: {e}")
                time.sleep(pause)

    # Fallback default high-CTR prompt if all API tiers fail (unquoted theme to prevent text hallucination)
    fallback_thumb = (
        "Semi-realistic 2D psychological abstract art illustration exploring the central theme of the mind. "
        "A contemplative human silhouette stands strictly centered before a colossal glowing surreal psychological mindscape, "
        "surrounded by intricate floating abstract geometry, luminous neural threads, and an overhead cinematic spotlight cone. "
        "High-contrast color grading with deep charcoal shadows and radiant amber yellow and electric teal illumination, "
        "wide 16:9 cinematic composition, powerful visual curiosity hook, 8k resolution, clean atmospheric depth."
    )
    logger.warning("Using robust fallback thumbnail prompt.")
    return fallback_thumb
