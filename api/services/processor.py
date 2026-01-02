import os
import subprocess
import requests

from core.config import (
    TMP_DIR,
    PYTHON_BIN,
    PROCESSOR_SCRIPT,
    DRIVE_SCOPES,
    DRIVE_CREDENTIALS_PATH,
    DRIVE_UPLOAD_FOLDER_ID,
)

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


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
# DOWNLOAD DRIVE (PUBLIC LINK)
# ======================
def download_drive(url, out_path):
    with requests.get(url, stream=True, timeout=120) as r:
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
        raise ValueError("absolute_end must be greater than absolute_start")

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
# CUT AUDIO (MASTER AUDIO)
# ======================
def cut_audio(src, out, start, end):
    dur = end - start
    if dur <= 0:
        raise ValueError("absolute_end must be greater than absolute_start")

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
# processorprolite-v1.py
# expects:
#   python script.py <input_video> <input_audio> <output_video>
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
# UPLOAD TO GOOGLE DRIVE
# ======================
def upload_to_drive(file_path):
    creds = Credentials.from_service_account_file(
        DRIVE_CREDENTIALS_PATH,
        scopes=DRIVE_SCOPES,
    )

    service = build("drive", "v3", credentials=creds)

    metadata = {
        "name": os.path.basename(file_path),
        "parents": [DRIVE_UPLOAD_FOLDER_ID],
    }

    media = MediaFileUpload(file_path, resumable=True)

    result = (
        service.files()
        .create(
            body=metadata,
            media_body=media,
            fields="id,webViewLink",
        )
        .execute()
    )

    return {
        "file_id": result["id"],
        "webViewLink": result.get("webViewLink"),
    }


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

        # 1️⃣ download video & audio (FULL)
        download_drive(video_url, video_raw)
        download_drive(audio_url, audio_raw)

        # 2️⃣ cut video & audio (TIMESTAMP SAMA)
        cut_video(video_raw, video_cut, start, end)
        cut_audio(audio_raw, audio_cut, start, end)

        # 3️⃣ run processor (subtitle + tracking + final mux)
        run_processor(video_cut, audio_cut, final)

        # 4️⃣ upload result to Drive
        drive_result = upload_to_drive(final)

        write_state(job_id, "done")

        return drive_result

    except Exception as e:
        write_state(job_id, "error")
        raise e

    finally:
        # cleanup temp files
        for p in [
            video_raw,
            video_cut,
            audio_raw,
            audio_cut,
        ]:
            if os.path.exists(p):
                os.remove(p)
