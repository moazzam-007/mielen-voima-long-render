"""
main.py
FastAPI Server & Async Pipeline Orchestrator for Mielen Voima Long Video Engine.
"""

import os
import sys
import uuid
import time
import asyncio
import logging
import shutil
import threading
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException, Header, Depends, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import requests

from config import (
    logger,
    JOBS_DIR,
    API_SECRET_KEY,
    PORT
)
from modules.gemini_engine import split_and_generate_prompts
from modules.audio_engine import generate_all_audio
from modules.image_engine import generate_all_images
from modules.thumbnail_engine import create_composite_thumbnail
from modules.subtitle_engine import generate_ass_subtitles
from modules.video_engine import assemble_long_video

app = FastAPI(
    title="Mielen Voima Long Video Engine",
    description="Automated 1080p Whiteboard Video Generator for Finnish YouTube Channel",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-Memory Job Registry
JOBS: Dict[str, Dict[str, Any]] = {}

# ── Concurrency Guard & Disk Hygiene (512MB RAM target) ────────────────────
RENDER_SLOT_LOCK = threading.Lock()
MAX_CONCURRENT_JOBS = 1
JOB_TTL_SECONDS = 1800  # 30 min retention for completed/failed jobs


def acquire_render_slot() -> bool:
    """Try to claim the single render slot without blocking. Returns True if acquired."""
    return RENDER_SLOT_LOCK.acquire(blocking=False)


def release_render_slot() -> None:
    """Release the render slot; safe to call even if not currently held."""
    try:
        RENDER_SLOT_LOCK.release()
    except RuntimeError:
        pass


def purge_expired_jobs() -> int:
    """Delete job dirs + registry entries older than JOB_TTL_SECONDS. Returns count purged."""
    now = time.time()
    purged = 0
    for job_id in list(JOBS.keys()):
        job = JOBS.get(job_id, {})
        # Skip actively processing jobs so a long render is never deleted mid-run.
        if job.get("status") == "processing":
            continue
        ref_time = job.get("completed_at") or job.get("created_at", now)
        try:
            age = now - float(ref_time)
        except (TypeError, ValueError):
            age = 0
        if age > JOB_TTL_SECONDS:
            try:
                job_dir = JOBS_DIR / job_id
                shutil.rmtree(job_dir, ignore_errors=True)
            except Exception:
                pass
            JOBS.pop(job_id, None)
            purged += 1
    if purged:
        logger.info(f"Purged {purged} expired job(s) (TTL {JOB_TTL_SECONDS}s).")
    return purged

class GenerateLongVideoRequest(BaseModel):
    script: str = Field(..., description="Full Finnish script text (continuous paragraph)")
    title: Optional[str] = Field("8 Merkkiä Siitä, Että Olet Yliälykäs", description="Video title")
    hook_top: Optional[str] = Field("8 MERKKIÄ", description="Thumbnail top hook text (2-3 words)")
    hook_highlight: Optional[str] = Field("OLETKO LIIAN ÄLYKÄS?", description="Thumbnail highlight text (2-3 words)")
    webhook_url: Optional[str] = Field(None, description="Optional n8n webhook URL to notify on completion")

def verify_api_key(x_api_key: Optional[str] = Header(None)):
    if API_SECRET_KEY:
        if not x_api_key or x_api_key != API_SECRET_KEY:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing X-API-Key header"
            )
    return True

def run_pipeline_worker(job_id: str, req: GenerateLongVideoRequest):
    """Synchronous background worker executing all pipeline stages.

    FastAPI runs plain `def` background tasks in a threadpool executor
    (starlette.concurrency.run_in_threadpool), keeping Uvicorn's event
    loop non-blocking for /health and /api/status during 15-20 min renders.
    """
    job = JOBS[job_id]
    job["status"] = "processing"
    job["progress"] = 5
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    try:
        # ── Step 1: Gemini Scene Chunking & Prompts (15%) ────────────────────
        job["step"] = "gemini_prompt_generation"
        job["progress"] = 10
        logger.info(f"[{job_id}] Starting Step 1: Gemini 3.8 Flash scene chunking...")

        scenes = split_and_generate_prompts(req.script)
        job["total_scenes"] = len(scenes)
        job["progress"] = 20

        # ── Step 2: Edge-TTS Audio Generation (35%) ──────────────────────────
        job["step"] = "audio_generation"
        logger.info(f"[{job_id}] Starting Step 2: Generating voiceover for {len(scenes)} scenes...")
        audio_dir = job_dir / "audio"
        scenes = asyncio.run(generate_all_audio(scenes, audio_dir))
        total_duration = sum(s["duration"] for s in scenes)
        job["duration_seconds"] = total_duration
        job["progress"] = 40

        # ── Step 3: Cloudflare FLUX.2 Klein 4B Images (70%) ──────────────────
        job["step"] = "image_generation"
        logger.info(f"[{job_id}] Starting Step 3: Generating {len(scenes)} images via FLUX.2 Klein 4B...")
        img_dir = job_dir / "images"
        scenes = generate_all_images(scenes, img_dir)
        job["progress"] = 70

        # ── Step 4: Composite Thumbnail Synthesis (80%) ─────────────────────
        job["step"] = "thumbnail_synthesis"
        logger.info(f"[{job_id}] Starting Step 4: Synthesizing 1280x720 thumbnail...")
        # Use first scene or representative scene visual for thumbnail
        key_img = Path(scenes[0]["image_path"])
        thumb_path = job_dir / "thumbnail.png"
        create_composite_thumbnail(key_img, req.hook_top, req.hook_highlight, thumb_path)
        job["progress"] = 80

        # ── Step 5: ASS Subtitle Generation (85%) ───────────────────────────
        job["step"] = "subtitle_generation"
        logger.info(f"[{job_id}] Starting Step 5: Generating ASS subtitles (Solid Black, Outline=0)...")
        sub_path = job_dir / "subtitles.ass"
        generate_ass_subtitles(scenes, sub_path)
        job["progress"] = 85

        # ── Step 6: FFmpeg TS Chunks & Video Assembly (100%) ─────────────────
        job["step"] = "video_assembly"
        logger.info(f"[{job_id}] Starting Step 6: Assembling memory-safe 1080p video...")
        final_video_path = job_dir / "final_video.mp4"
        assemble_long_video(scenes, sub_path, job_dir / "work", final_video_path)

        # Mark Completed
        job["status"] = "completed"
        job["step"] = "finished"
        job["progress"] = 100
        job["video_path"] = str(final_video_path)
        job["thumbnail_path"] = str(thumb_path)
        job["video_size_mb"] = round(final_video_path.stat().st_size / (1024 * 1024), 2)
        job["completed_at"] = time.time()
        logger.info(f"[{job_id}] PIPELINE COMPLETED SUCCESSFULLY! Size: {job['video_size_mb']} MB")

        # Optional Webhook Notification to n8n
        if req.webhook_url:
            try:
                logger.info(f"[{job_id}] Sending completion webhook to {req.webhook_url}...")
                payload = {
                    "job_id": job_id,
                    "status": "completed",
                    "title": req.title,
                    "duration_seconds": job["duration_seconds"],
                    "video_size_mb": job["video_size_mb"],
                    "download_video_url": f"/api/download/{job_id}/video",
                    "download_thumbnail_url": f"/api/download/{job_id}/thumbnail"
                }
                requests.post(req.webhook_url, json=payload, timeout=10)
            except Exception as e:
                logger.warning(f"[{job_id}] Webhook dispatch error: {e}")

    except Exception as e:
        logger.exception(f"[{job_id}] Pipeline failed: {e}")
        job["status"] = "failed"
        job["error"] = str(e)
        job["progress"] = 0
        job["completed_at"] = time.time()
        shutil.rmtree(job_dir, ignore_errors=True)
    finally:
        release_render_slot()

@app.get("/health")
def healthcheck():
    purge_expired_jobs()
    return {
        "status": "ok",
        "service": "mielen-voima-long-video-engine",
        "active_jobs": len(JOBS)
    }

@app.post("/api/generate-long-video")
async def generate_long_video(
    req: GenerateLongVideoRequest,
    background_tasks: BackgroundTasks,
    authenticated: bool = Depends(verify_api_key)
):
    """
    Submits a new long video render task. Returns job_id immediately.
    """
    purge_expired_jobs()
    if len(req.script.strip()) < 50:
        raise HTTPException(status_code=400, detail="Script text is too short!")

    if not acquire_render_slot():
        raise HTTPException(
            status_code=429,
            detail="Render engine busy. A video job is currently in progress."
        )

    job_id = f"mv_{uuid.uuid4().hex[:8]}"
    JOBS[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0,
        "step": "pending",
        "title": req.title,
        "created_at": time.time(),
        "error": None
    }

    logger.info(f"Queued new render job: {job_id} | Title: {req.title}")
    background_tasks.add_task(run_pipeline_worker, job_id, req)

    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Long video generation queued successfully",
        "status_url": f"/api/status/{job_id}"
    }

@app.get("/api/status/{job_id}", dependencies=[Depends(verify_api_key)])
def get_job_status(job_id: str):
    """Returns current status and progress of a render job."""
    purge_expired_jobs()
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    res = {
        "job_id": job_id,
        "status": job["status"],
        "progress": job.get("progress", 0),
        "step": job.get("step", ""),
        "total_scenes": job.get("total_scenes"),
        "duration_seconds": job.get("duration_seconds"),
        "video_size_mb": job.get("video_size_mb"),
        "error": job.get("error")
    }

    if job["status"] == "completed":
        res["download_video_url"] = f"/api/download/{job_id}/video"
        res["download_thumbnail_url"] = f"/api/download/{job_id}/thumbnail"

    return res

@app.get("/api/download/{job_id}/video", dependencies=[Depends(verify_api_key)])
def download_video(job_id: str):
    """Serves the final 1080p MP4 subtitled video."""
    job = JOBS.get(job_id)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="Video not ready or job not found")

    p = Path(job["video_path"])
    if not p.exists():
        raise HTTPException(status_code=404, detail="Video file missing on disk")

    return FileResponse(
        p,
        media_type="video/mp4",
        filename=f"Mielen_Voima_{job_id}.mp4"
    )

@app.get("/api/download/{job_id}/thumbnail", dependencies=[Depends(verify_api_key)])
def download_thumbnail(job_id: str):
    """Serves the final 1280x720 composite thumbnail."""
    job = JOBS.get(job_id)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="Thumbnail not ready or job not found")

    p = Path(job["thumbnail_path"])
    if not p.exists():
        raise HTTPException(status_code=404, detail="Thumbnail file missing on disk")

    return FileResponse(
        p,
        media_type="image/png",
        filename=f"Thumbnail_{job_id}.png"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
