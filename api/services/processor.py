import os
import subprocess
import requests

from core.config import (
    TMP_DIR,
    PYTHON_BIN,
    PROCESSOR_SCRIPT,
    RCLONE_REMOTE,
)

# ======================
# JOB STATE
# ======================
def state_path(job_id):
    return f"{TMP_DIR}/{job_id}.state"


def write_state(job_id, state):
    with open(state_path(job_id), "w") as f:
        f.write(state)


def read_state(job_id):
    if not os.path.exists(state_path(job_id)):
        return None
    return open(state_path(job_id)).read().strip()


# ======================
# DOWNLOAD FILE (PUBLIC LINK)
# ======================
def download_file(url, out_path):
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)


# ======================
# CUT VIDEO
# ======================
def cut_video(src, out, start, end):
    dur = end - start
    if dur <= 0:
        raise ValueError("end must be greater than start")

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", src,
            "-t", str(dur),
            "-c:v", "libx264",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            out,
        ],
        check=True,
    )


# ======================
# CUT AUDIO
# ======================
def cut_audio(src, out, start, end):
    dur = end - start
    if dur <= 0:
        raise ValueError("end must be greater than start")

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", src,
            "-t", str(dur),
            "-ar", "16000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            out,
        ],
        check=True,
    )


# ======================
# RUN PROCESSORPROLITE
# ======================
def run_processor(input_video, input_audio, output_video):
    subprocess.run(
        [
            PYTHON_BIN,
            PROCESSOR_SCRIPT,
            input_video,
            input_audio,
            output_video,
        ],
        check=True,
    )


# ======================
# UPLOAD VIA RCLONE (OAUTH USER)
# ======================
def upload_with_rclone(local_file, remote_dir):
    subprocess.run(
        [
            "rclone",
            "move",
            local_file,
            remote_dir,
            "--progress",
            "--transfers", "1",
        ],
        check=True,
    )


# ======================
# MAIN JOB
# ======================
def process_job(job_id, video_url, audio_url, start, end):
    video_raw = f"{TMP_DIR}/{job_id}_video_raw.mp4"
    video_cut = f"{TMP_DIR}/{job_id}_video_cut.mp4"

    audio_raw = f"{TMP_DIR}/{job_id}_audio_raw.wav"
    audio_cut = f"{TMP_DIR}/{job_id}_audio_cut.wav"

    final = f"{TMP_DIR}/{job_id}_final.mp4"

    try:
        write_state(job_id, "running")

        # 1️⃣ DOWNLOAD VIDEO & AUDIO
        download_file(video_url, video_raw)
        download_file(audio_url, audio_raw)

        # 2️⃣ CUT VIDEO & AUDIO
        cut_video(video_raw, video_cut, start, end)
        cut_audio(audio_raw, audio_cut, start, end)

        # 3️⃣ PROCESS (SUBTITLE + TRACKING + FINAL RENDER)
        run_processor(video_cut, audio_cut, final)

        # 4️⃣ UPLOAD RESULT VIA RCLONE
        upload_with_rclone(final, RCLONE_REMOTE)

        write_state(job_id, "done")

        return {
            "status": "done",
            "remote": RCLONE_REMOTE,
            "file": os.path.basename(final),
        }

    except Exception as e:
        write_state(job_id, f"error: {e}")
        return {
            "status": "error",
            "error": str(e),
        }

    finally:
        # cleanup temp files (KEEP final if upload failed)
        for p in [
            video_raw,
            video_cut,
            audio_raw,
            audio_cut,
        ]:
            if os.path.exists(p):
                os.remove(p)
