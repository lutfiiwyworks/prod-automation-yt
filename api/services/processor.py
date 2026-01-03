import os
import subprocess
import requests
import time

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
# SAFE DOWNLOAD (BLOCKING)
# ======================
def download_file(url, out_path):
    tmp_path = out_path + ".part"

    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(tmp_path, "wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)
                    f.flush()
                    os.fsync(f.fileno())

    os.rename(tmp_path, out_path)


# ======================
# VALIDATE MP4
# ======================
def assert_valid_mp4(path, retry=5, wait=2):
    for i in range(retry):
        try:
            subprocess.run(
                ["ffprobe", "-v", "error", path],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except subprocess.CalledProcessError:
            if i == retry - 1:
                raise RuntimeError(f"Invalid MP4 (moov atom missing): {path}")
            time.sleep(wait)


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


# ======================
# CUT VIDEO (SAFE)
# ======================
def cut_video(src, out, start, end):
    duration = get_duration(src)

    if start >= duration:
        raise ValueError("start >= video duration")

    safe_end = min(end, duration - 0.2)
    dur = safe_end - start

    if dur <= 0:
        raise ValueError("invalid cut duration")

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", src,
            "-ss", str(start),
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
    duration = get_duration(src)

    if start >= duration:
        raise ValueError("start >= audio duration")

    safe_end = min(end, duration - 0.2)
    dur = safe_end - start

    if dur <= 0:
        raise ValueError("invalid audio cut duration")

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", src,
            "-ss", str(start),
            "-t", str(dur),
            "-ar", "16000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            out,
        ],
        check=True,
    )


# ======================
# RUN PROCESSOR
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
# UPLOAD VIA RCLONE
# ======================
def upload_with_rclone(local_file, remote_dir):
    subprocess.run(
        [
            "rclone",
            "move",
            local_file,
            remote_dir,
            "--transfers", "1",
            "--checkers", "1",
            "--progress",
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
        write_state(job_id, "downloading")

        # 1️⃣ DOWNLOAD
        download_file(video_url, video_raw)
        download_file(audio_url, audio_raw)

        # 2️⃣ VALIDATE (ANTI moov atom bug)
        write_state(job_id, "validating")
        assert_valid_mp4(video_raw)
        assert_valid_mp4(audio_raw)

        # 3️⃣ CUT
        write_state(job_id, "cutting")
        cut_video(video_raw, video_cut, start, end)
        cut_audio(audio_raw, audio_cut, start, end)

        # 4️⃣ PROCESS
        write_state(job_id, "processing")
        run_processor(video_cut, audio_cut, final)

        # 5️⃣ UPLOAD
        write_state(job_id, "uploading")
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
        # cleanup intermediates only
        for p in [video_raw, video_cut, audio_raw, audio_cut]:
            if os.path.exists(p):
                os.remove(p)
