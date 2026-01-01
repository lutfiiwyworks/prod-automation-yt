import subprocess
import os
from core.config import AUDIO_CACHE

def get_video_id(url: str) -> str:
    return subprocess.check_output(
        ["yt-dlp", "--print", "id", "--no-playlist", url],
        text=True
    ).strip()

def download_audio(url: str):
    vid_id = get_video_id(url)
    file_path = os.path.join(AUDIO_CACHE, f"full_audio_{vid_id}.m4a")

    status = "cached"
    if not os.path.exists(file_path):
        status = "downloaded"
        subprocess.run(
            [
                "yt-dlp",
                "--force-ipv4",
                "-f", "bestaudio[ext=m4a]/bestaudio",
                "--extract-audio",
                "--audio-format", "m4a",
                "-o", file_path,
                url
            ],
            check=True
        )

    return status, vid_id, file_path
