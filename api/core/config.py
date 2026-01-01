import os

# 🔒 FIXED PATH (DOCKER SAFE)
TMP_DIR = "/app/tmp"
AUDIO_CACHE = os.path.join(TMP_DIR, "audio_master")

os.makedirs(AUDIO_CACHE, exist_ok=True)
