import os
import subprocess
import requests
from core.config import TMP_DIR, PYTHON_BIN, PROCESSOR_SCRIPT

def state_path(job_id):
    return f"{TMP_DIR}/{job_id}.state"

def write_state(job_id, state):
    with open(state_path(job_id), "w") as f:
        f.write(state)

def read_state(job_id):
    if not os.path.exists(state_path(job_id)):
        return None
    return open(state_path(job_id)).read().strip()

def download_drive(url, out_path):
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)

def cut_video(src, out, start, end):
    dur = end - start
    if dur <= 0:
        raise ValueError("invalid duration")

    subprocess.run([
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", src,
        "-t", str(dur),
        "-c:v", "libx264",
        "-c:a", "aac",
        out
    ], check=True)

def run_processor(input_video, output_video):
    subprocess.run(
        [
            PYTHON_BIN,
            PROCESSOR_SCRIPT,
            input_video,
            output_video
        ],
        check=True
    )

def process_job(job_id, drive_url, start, end):
    raw = f"{TMP_DIR}/{job_id}_raw.mp4"
    cut = f"{TMP_DIR}/{job_id}_cut.mp4"
    final = f"{TMP_DIR}/{job_id}_final.mp4"

    try:
        write_state(job_id, "running")

        download_drive(drive_url, raw)
        cut_video(raw, cut, start, end)

        # 🔥 INI YANG LU MAKSUD PROCESS
        run_processor(cut, final)

        write_state(job_id, "done")

    except Exception as e:
        write_state(job_id, "error")
        raise e

    finally:
        if os.path.exists(raw):
            os.remove(raw)
        if os.path.exists(cut):
            os.remove(cut)
