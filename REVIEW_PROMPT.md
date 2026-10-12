# Comprehensive Review & Audit Prompt for Mielen Voima Long Video Automation

Copy and paste the prompt below into Claude 3.7 Sonnet, ChatGPT, or your preferred senior reviewer LLM to get a deep, rigorous engineering audit of the entire codebase and n8n workflow.

---

```markdown
You are an elite Senior Full-Stack Media Automation Architect and AI Systems Engineer. 
I need you to perform a thorough, critical code and architecture review of an end-to-end automated YouTube long-video creation and publishing system.

### 🎯 Project Overview & Goal
- **Channel**: Mielen Voima (@Mielen_Voima) — Finnish psychology, stoic philosophy, and deep thinking.
- **Target Cadence & Format**: Daily 1 automated 1080p long-form video (3 to 5 minutes duration, ~40-50 scenes) + custom 1280x720 thumbnail.
- **Workflow Pipeline**: 
  1. Content source: 30-day Google Sheet calendar containing pre-translated Finnish scripts.
  2. Orchestrator: n8n workflow triggered on a daily schedule (19:00 Finnish time).
  3. Video Rendering Factory: Render.com FastAPI web service (`mielen-voima-long-render`) running on Docker (Frankfurt region, 512MB RAM free tier).
  4. Publishing: Automatically uploads 1080p MP4 to YouTube + uploads custom thumbnail via YouTube OAuth API + updates Google Sheet row + sends Telegram alert.
  5. ZERO manual human intervention required.

---

### 🧱 System Architecture & Implementation Details

#### 1. Rendering Engine (`mielen-voima-long-render`)
- **Web Framework**: FastAPI (`main.py`) with asynchronous background job worker, healthcheck `/health`, submit `/api/generate-long-video`, status polling `/api/status/{job_id}`, and binary file downloads `/api/download/{job_id}/video` & `/thumbnail`.
- **Gemini 3.8 Flash (`modules/gemini_engine.py`)**:
  - Chunks full Finnish script paragraph into 40–50 natural storytelling scenes.
  - Strict Prompt Rules:
    * 30 to 50 words per `scene_prompt`.
    * ZERO text inside image (prevents 4B model garbled text artifacts).
    * Max 1 bare stick figure + max 1 to 2 concrete physical objects + 1 simple action verb.
    * Positive phrasing only (never "no/not/without/zero").
    * Dynamic composition cycling (centered, left_third, right_third, close_up, wide_small_figure, top_down).
    * Code-level boilerplate assembly: `STYLE_PREFIX` (pure white canvas #FFFFFF, stickman anatomy) + `scene_prompt` + `STYLE_SUFFIX` (upper 75% placement, bottom quarter left empty for subtitles).
- **Edge-TTS Audio (`modules/audio_engine.py`)**:
  - Voice: Finnish `fi-FI-HarriNeural` (`-2%` rate).
  - Trailing silence trimming with `pydub` `detect_leading_silence` on reversed audio, retaining exact 100ms natural gap and 15ms anti-pop micro fade-out.
- **Cloudflare FLUX.2 [klein] 4B (`modules/image_engine.py`)**:
  - Calls `@cf/black-forest-labs/flux-2-klein-4b` via `multipart/form-data`.
  - Multi-account rotation with automatic failover across 3 Cloudflare accounts (30,000 Neurons/day free limit = ~280 images/day).
- **Thumbnail Synthesis (`modules/thumbnail_engine.py`)**:
  - Generates 1280x720 composite image using Pillow:
    * Left side: Bold black text + Amber Yellow (`#FBBF24`) rounded highlight box.
    * Right side: Scaled FLUX.2 doodle stickman with ample breathing room.
- **ASS Subtitles (`modules/subtitle_engine.py`)**:
  - Pure solid black font (`PrimaryColour=&H00000000`), **ZERO white outline** (`Outline=0`, `Shadow=0`), centered bottom.
- **Video Assembly (`modules/video_engine.py`)**:
  - Renders memory-safe individual `.ts` transport stream chunks (<80MB RAM usage).
  - Stream-copy concatenation into raw MP4.
  - Burns in ASS subtitles using FFmpeg.
- **Deployment**: `Dockerfile` and `render.yaml` configured for Render.com free tier.

#### 2. Orchestration (`mielen_voima_long_video_workflow.json`)
- 19-node n8n workflow:
  * Schedule trigger (19:00 Finnish time) -> Wake Render engine (`GET /health`) -> Wait 45s spinup -> Read pending row from Google Sheet.
  * Dispatch render job (`POST /api/generate-long-video`) -> Initial wait 90s -> Poll status loop (30s interval, up to 45 attempts / 22 mins).
  * Download MP4 video -> Download PNG thumbnail.
  * Upload video to YouTube with title, description, tags, category 27.
  * Upload custom thumbnail to YouTube via OAuth HTTP Request (`POST https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={{ $json.id }}`).
  * Update Google Sheet row status to "published" with YouTube URL.
  * Telegram alert with live link, duration, and file size.

---

### 🔍 Review Objectives & Questions for You:
1. **Robustness & Error Handling**: Are there edge cases where the FastAPI job runner or n8n workflow could hang, deadlock, or leak memory/disk space on Render's 512MB RAM environment?
2. **FLUX.2 Klein 4B Prompt Fidelity**: Does the prompt assembly strictly prevent hallucinations, unwanted backgrounds, or model confusion?
3. **Audio-Video Synchronization**: Are there potential desync issues between Edge-TTS audio chunk durations and FFmpeg `.ts` chunk generation?
4. **YouTube & Cloudflare API Constraints**: Are rate limits, timeouts, and quota thresholds safely mitigated?
5. **Architectural Improvements**: What high-leverage refactorings or safeguards would you recommend before putting this into a 30-day autonomous daily run?
```
