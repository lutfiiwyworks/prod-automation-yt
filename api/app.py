import os
import uuid
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

from schemas.jobs import (
    DownloadRequest,
    DownloadResponse,
    ProcessRequest
)

from services.downloader import download_audio
from services.processor import run_processor
from services.media_prepare import prepare_media
from services.render import render_short
from services.job_store import get_job, set_job


app = FastAPI(
    title="ProcessorProLite API",
    version="1.0.0"
)

# =========================
# REQUEST MODELS
# =========================

class RenderRequest(BaseModel):
    video_path: str
    absolute_start: float
    absolute_end: float


class PrepareRequest(BaseModel):
    url: str
    start_detik: int
    end_detik: int


# =========================
# BACKGROUND WRAPPER
# =========================

def prepare_media_wrapper(req: PrepareRequest, job_id: str):
    """
    Wrapper agar:
    - prepare_media jalan di background
    - job status ke-update
    - error ketangkep
    """
    try:
        result = prepare_media(
            req.url,
            req.start_detik,
            req.end_detik,
            job_id
        )

        # prepare_media SUDAH set_job step by step
        # di sini kita pastiin final state aman
        set_job(job_id, result)

    except Exception as e:
        set_job(job_id, {
            "status": "error",
            "step": "failed",
            "error": str(e)
        })


# =========================
# ENDPOINTS
# =========================

@app.post("/prepare_media")
def api_prepare(req: PrepareRequest, bg: BackgroundTasks):
    job_id = str(uuid.uuid4())

    # INIT JOB
    set_job(job_id, {
        "status": "queued",
        "step": "init",
        "progress": 0,
        "url": req.url
    })

    bg.add_task(
        prepare_media_wrapper,
        req,
        job_id
    )

    return {
        "status": "processing",
        "job_id": job_id
    }


@app.get("/job_status/{job_id}")
def job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        return {
            "status": "unknown",
            "message": "job_id not found"
        }
    return job


@app.post("/render_short")
def api_render(req: RenderRequest):
    return render_short(
        req.video_path,
        req.absolute_start,
        req.absolute_end
    )


@app.post("/download_audio", response_model=DownloadResponse)
def api_download_audio(req: DownloadRequest):
    try:
        status, vid_id, path = download_audio(req.url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "status": status,
        "video_id": vid_id,
        "full_file_path": path,
        "start_detik": req.start_detik,
        "end_detik": req.end_detik
    }


@app.post("/process")
def api_process(req: ProcessRequest):
    if not os.path.exists(req.input_path):
        raise HTTPException(status_code=400, detail="Input file not found")

    try:
        run_processor(req.input_path, req.output_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "status": "ok",
        "output": req.output_path
    }
