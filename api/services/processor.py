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
# DOWNLOAD DRIVE (PUBLIC)
# ======================
def download_drive(url, out_path):
    with requests.get(url, stream=True, timeout=60) as r:
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
            "ffmpeg",
            "-y",
            "-ss",
            str(start),
            "-i",
            src,
            "-t",
            str(dur),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-c:a",
            "aac",
            out,
        ],
        check=True,
    )


# ======================
# RUN PROCESSORPROLITE
# ======================
def run_processor(input_video, output_video):
    subprocess.run(
        [
            PYTHON_BIN,
            PROCESSOR_SCRIPT,
            input_video,
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
def process_job(job_id, drive_url, start, end):
    raw = f"{TMP_DIR}/{job_id}_raw.mp4"
    cut = f"{TMP_DIR}/{job_id}_cut.mp4"
    final = f"{TMP_DIR}/{job_id}_final.mp4"

    try:
        write_state(job_id, "running")

        # 1️⃣ download video
        download_drive(drive_url, raw)

        # 2️⃣ cut
        cut_video(raw, cut, start, end)

        # 3️⃣ run processorprolite
        run_processor(cut, final)

        # 4️⃣ upload to Google Drive
        drive_result = upload_to_drive(final)

        write_state(job_id, "done")

        return drive_result

    except Exception as e:
        write_state(job_id, "error")
        raise e

    finally:
        # cleanup temp
        for p in [raw, cut]:
            if os.path.exists(p):
                os.remove(p)
