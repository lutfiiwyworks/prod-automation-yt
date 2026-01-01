import os
import subprocess

BASE_TMP = "/app/tmp"
FINAL_DIR = os.path.join(BASE_TMP, "final")
os.makedirs(FINAL_DIR, exist_ok=True)

def render_short(video_path: str, start: float, end: float):
    name = os.path.basename(video_path).replace(".mp4", "")
    out = os.path.join(
        FINAL_DIR,
        f"{name}_{int(start)}_{int(end)}.mp4"
    )

    subprocess.run([
        "ffmpeg", "-y",
        "-ss", str(start),
        "-to", str(end),
        "-i", video_path,
        "-c", "copy",
        out
    ], check=True)

    # 🔥 PATH UNTUK N8N
    return {
        "final_path": out.replace("/app/tmp", "/data/tmp")
    }
