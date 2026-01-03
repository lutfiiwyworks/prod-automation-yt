import os
import subprocess
import requests
import shutil

from api.core.config import (
    TMP_DIR,
    PYTHON_BIN,
    PROCESSOR_SCRIPT,
    RCLONE_REMOTE,
)

# ==================================================
# PATH HELPERS
# ==================================================
def job_dir(job_id):
    base = f"{TMP_DIR}/{job_id}"
    os.makedirs(base, exist_ok=True)
    return base

def stage_path(job_id, stage, filename):
    path = f"{job_dir(job_id)}/{stage}"
    os.makedirs(path, exist_ok=True)
    return f"{path}/{filename}"

def state_path(job_id):
    return f"{job_dir(job_id)}/job.state"

def write_state(job_id, state):
    with open(state_path(job_id), "w") as f:
        f.write(state)

# ==================================================
# DOWNLOAD (ATOMIC)
# ==================================================
def download_file(url, out_path):
    tmp = out_path + ".part"

    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)
                    f.flush()
                    os.fsync(f.fileno())

    os.rename(tmp, out_path)

# ==================================================
# DURATION
# ==================================================
def get_duration(path):
    out = subprocess.check_output(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=nokey=1:noprint_wrappers=1",
            path,
        ]
    )
    return float(out)

# ==================================================
# CUT VIDEO (VISUAL ONLY, FULL TRANSCODE HQ)
# ==================================================
def cut_video_visual_only(src, out, start, end):
    duration = get_duration(src)
    safe_end = min(end, duration - 0.2)
    dur = safe_end - start
    if dur <= 0:
        raise ValueError("invalid video cut duration")

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-err_detect", "ignore_err",
            "-fflags", "+genpts",
            "-ss", str(start),
            "-i", src,
            "-t", str(dur),

            "-map", "0:v:0",
            "-an",  # 🔥 buang audio video sepenuhnya

            "-c:v", "libx264",
            "-preset", "slow",     # quality > speed
            "-crf", "16",           # HQ
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",

            out,
        ],
        check=True,
    )

# ==================================================
# CUT AUDIO (SOURCE OF TRUTH, NO FILTER HERE)
# ==================================================
def cut_audio(src, out, start, end):
    duration = get_duration(src)
    safe_end = min(end, duration - 0.2)
    dur = safe_end - start
    if dur <= 0:
        raise ValueError("invalid audio cut duration")

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", src,
            "-t", str(dur),

            "-ar", "16000",
            "-ac", "1",
            "-c:a", "wavpack",   # lossless, biar processorprolite kerja optimal

            out,
        ],
        check=True,
    )

# ==================================================
# PROCESS AUDIO (processorprolite = EQ + COMPAND + LOUDNORM)
# ==================================================
def run_processor(video_cut, audio_cut, out_video):
    subprocess.run(
        [
            PYTHON_BIN,
            PROCESSOR_SCRIPT,
            video_cut,
            audio_cut,
            out_video,
        ],
        check=True,
    )

# ==================================================
# UPLOAD
# ==================================================
def upload_with_rclone(local_file, remote_dir):
    subprocess.run(
        [
            "rclone",
            "move",
            local_file,
            remote_dir,
            "--transfers", "1",
            "--checkers", "1",
        ],
        check=True,
    )

# ==================================================
# MAIN ENTRY
# ==================================================
def process_job(job_id, video_url, audio_url, start, end):
    try:
        write_state(job_id, "downloading")

        video_raw = stage_path(job_id, "input", "video.mp4")
        audio_raw = stage_path(job_id, "input", "audio.wav")

        video_cut = stage_path(job_id, "cut", "video.mp4")
        audio_cut = stage_path(job_id, "cut", "audio.wav")

        final = stage_path(job_id, "final", "output.mp4")

        # 1️⃣ DOWNLOAD
        download_file(video_url, video_raw)
        download_file(audio_url, audio_raw)

        # 2️⃣ CUT
        write_state(job_id, "cutting")
        cut_video_visual_only(video_raw, video_cut, start, end)
        cut_audio(audio_raw, audio_cut, start, end)

        # 3️⃣ PROCESS (AUDIO FILTERS + LOUDNORM ADA DI processorprolite)
        write_state(job_id, "processing")
        run_processor(video_cut, audio_cut, final)

        # 4️⃣ UPLOAD
        write_state(job_id, "uploading")
        upload_with_rclone(final, RCLONE_REMOTE)

        write_state(job_id, "done")

        return {
            "status": "done",
            "file": os.path.basename(final),
            "remote": RCLONE_REMOTE,
        }

    except Exception as e:
        write_state(job_id, f"error: {e}")
        return {
            "status": "error",
            "error": str(e),
        }

    finally:
        # cleanup only if success
        try:
            if os.path.exists(state_path(job_id)):
                if open(state_path(job_id)).read() == "done":
                    shutil.rmtree(job_dir(job_id), ignore_errors=True)
        except Exception:
            pass
