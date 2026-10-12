# Mielen Voima Long Video Render Engine (`@Mielen_Voima`)

Fully automated 1080p whiteboard video rendering service for the Finnish psychology YouTube channel **Mielen Voima**.

---

## 🚀 Key Features & Pipeline Stages

1. **Gemini 3.8 Flash Scene Chunking (`modules/gemini_engine.py`)**:
   - Takes raw Finnish script paragraph, splits it into 40–50 natural storytelling scenes.
   - Generates lean, 30–50 word positive scene prompts.
   - Injects standardized boilerplate via code:
     - `STYLE_PREFIX`: Pure white `#FFFFFF` canvas, black doodle outlines, bare stickman.
     - `STYLE_SUFFIX`: Upper 75% placement, bottom quarter left completely empty for subtitles.
   - Zero text inside generated images (avoids AI spelling distortions).

2. **Edge-TTS Audio Engine (`modules/audio_engine.py`)**:
   - Finnish voiceover with `fi-FI-HarriNeural` (`-2%` rate).
   - Trailing silence trimming with 100ms natural gap and 15ms anti-pop micro fade-out.

3. **Cloudflare AI FLUX.2 [klein] 4B (`modules/image_engine.py`)**:
   - Ultra-fast whiteboard doodle image generation via `@cf/black-forest-labs/flux-2-klein-4b`.
   - Multipart form-data API call with automatic 3-account rotation and failover.
   - Free tier compliant (30,000 Neurons/day across 3 accounts = ~280 images/day).

4. **Composite Thumbnail Engine (`modules/thumbnail_engine.py`)**:
   - Synthesizes 1280x720 YouTube thumbnail:
     - Left side: Bold black hook text + Amber Yellow (`#FBBF24`) highlight box.
     - Right side: Clean FLUX.2 doodle illustration.

5. **Pure Solid Black Subtitles (`modules/subtitle_engine.py`)**:
   - Advanced SubStation Alpha (`.ass`) with `Outline=0` and `Shadow=0`.
   - Pure solid black text, centered bottom alignment.

6. **Memory-Safe Video Assembler (`modules/video_engine.py`)**:
   - Renders individual `.ts` transport stream segments (<80MB RAM usage).
   - Concatenates via stream-copy into 1080p MP4.
   - Burns in ASS subtitles with FFmpeg.
   - 100% safe for Render.com free tier (512MB RAM limit).

---

## 🛠️ API Endpoints

- `GET /health` -> Healthcheck endpoint
- `POST /api/generate-long-video` -> Starts async video render job
  ```json
  {
    "script": "Full Finnish script paragraph...",
    "title": "8 Merkkiä Siitä, Että Olet Yliälykäs",
    "hook_top": "8 MERKKIÄ",
    "hook_highlight": "OLETKO LIIAN ÄLYKÄS?",
    "webhook_url": "https://your-n8n.webhook/notify"
  }
  ```
  Returns:
  ```json
  {
    "job_id": "mv_1a2b3c4d",
    "status": "queued",
    "status_url": "/api/status/mv_1a2b3c4d"
  }
  ```
- `GET /api/status/{job_id}` -> Checks progress (0 to 100%) and current step.
- `GET /api/download/{job_id}/video` -> Downloads final subtitled MP4 video.
- `GET /api/download/{job_id}/thumbnail` -> Downloads final 1280x720 thumbnail PNG.

---

## 📦 Local Setup & Testing

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure .env with your credentials
# (Copy from .env.example)

# 3. Start local development server
python main.py
```

---

## ☁️ Deploy to Render.com

1. Push this directory to your GitHub repository (e.g. `mielen-voima-long-render`).
2. In Render.com Dashboard:
   - Click **New** -> **Blueprint**.
   - Select your repository.
   - Render will detect `render.yaml` and set up the Docker web service in Frankfurt.
3. Add Environment Variables:
   - `CF_ACCOUNT_ID_1`, `CF_API_TOKEN_1`
   - `CF_ACCOUNT_ID_2`, `CF_API_TOKEN_2`
   - `CF_ACCOUNT_ID_3`, `CF_API_TOKEN_3`
   - `GEMINI_API_KEY`
   - `API_SECRET_KEY`
