import os
import subprocess
from services.job_store import set_job

# =========================
# PROD PATH (CONTAINER)
# =========================
BASE_TMP = "/app/tmp"

AUDIO_DIR = os.path.join(BASE_TMP, "audio")
AUDIO_CUT_DIR = os.path.join(BASE_TMP, "audio_cut")
VIDEO_MASTER_DIR = os.path.join(BASE_TMP, "video_master")

os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(AUDIO_CUT_DIR, exist_ok=True)
os.makedirs(VIDEO_MASTER_DIR, exist_ok=True)

# =========================
# YT-DLP CONFIG
# =========================
YTDLP_COOKIES = os.getenv("YTDLP_COOKIES")
if not YTDLP_COOKIES or not os.path.exists(YTDLP_COOKIES):
    raise RuntimeError("YTDLP_COOKIES env not set or cookies.txt not found")

YTDLP_BASE = [
    "yt-dlp",
    "--cookies", YTDLP_COOKIES,

    # Browser-like fingerprint
    "--user-agent",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36",

    "--add-header", "Accept-Language:en-US,en;q=0.9",
    "--add-header", "Referer:https://www.youtube.com/"
]

# =========================
# PATH TRANSLATOR (API ➜ n8n)
# =========================
def api_to_n8n(path: str) -> str:
    return path.replace("/app/tmp", "/data/tmp")

# =========================
# MAIN
# =========================
def prepare_media(url: str, start_detik: int, end_detik: int, job_id: str) -> dict:
    """
    FINAL PROD VERSION
    - yt-dlp + cookies + UA
    - cache-aware
    - job monitoring friendly
    """

    # -------------------------
    # STEP 1 — FETCH VIDEO ID
    # -------------------------
    try:
        set_job(job_id, {
            "status": "processing",
            "step": "fetch_video_id",
            "progress": 5
        })

        vid = subprocess.check_output(
            YTDLP_BASE + [
                "--print", "id",
                "--no-playlist",
                url
            ],
            stderr=subprocess.STDOUT,
            text=True
        ).strip()

    except subprocess.CalledProcessError as e:
        set_job(job_id, {
            "status": "error",
            "step": "yt_dlp_blocked",
            "error": e.output
        })
        raise RuntimeError(e.output)

    # -------------------------
    # PATH SETUP
    # -------------------------
    video_master = os.path.join(VIDEO_MASTER_DIR, f"master_{vid}.mp4")
    audio_full = os.path.join(AUDIO_DIR, f"full_{vid}.m4a")
    audio_cut = os.path.join(
        AUDIO_CUT_DIR,
        f"audio_{vid}_{start_detik}_{end_detik}.m4a"
    )

    # -------------------------
    # STEP 2 — VIDEO MASTER
    # -------------------------
    if not os.path.exists(video_master):
        set_job(job_id, {
            "step": "download_video",
            "progress": 20
        })

        subprocess.run(
            YTDLP_BASE + [
                "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b",
                "--merge-output-format", "mp4",
                "-o", video_master,
                url
            ],
            check=True
        )
    else:
        set_job(job_id, {
            "step": "video_cached",
            "progress": 30
        })

    # -------------------------
    # STEP 3 — AUDIO FULL
    # -------------------------
    if not os.path.exists(audio_full):
        set_job(job_id, {
            "step": "download_audio",
            "progress": 50
        })

        subprocess.run(
            YTDLP_BASE + [
                "-f", "bestaudio[ext=m4a]/bestaudio",
                "--extract-audio",
                "--audio-format", "m4a",
                "-o", audio_full,
                url
            ],
            check=True
        )
    else:
        set_job(job_id, {
            "step": "audio_cached",
            "progress": 60
        })

    # -------------------------
    # STEP 4 — AUDIO CUT
    # -------------------------
    if not os.path.exists(audio_cut):
        set_job(job_id, {
            "step": "cut_audio",
            "progress": 80
        })

        subprocess.run([
            "ffmpeg", "-y",
            "-i", audio_full,
            "-ss", str(start_detik),
            "-to", str(end_detik),
            "-c", "copy",
            audio_cut
        ], check=True)
    else:
        set_job(job_id, {
            "step": "audio_cut_cached",
            "progress": 90
        })

    # -------------------------
    # DONE
    # -------------------------
    result = {
        "status": "done",
        "job_id": job_id,
        "video_id": vid,

        # PATH UNTUK n8n
        "video_full_path": api_to_n8n(video_master),
        "audio_full_path": api_to_n8n(audio_full),
        "audio_cut_path": api_to_n8n(audio_cut),

        "audio_base_start": start_detik
    }

    set_job(job_id, {
        **result,
        "step": "completed",
        "progress": 100
    })

    return result
