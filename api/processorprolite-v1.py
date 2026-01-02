import sys
import os
import subprocess
import math
import cv2
import numpy as np
import mediapipe as mp
from faster_whisper import WhisperModel
import tempfile

# =========================
# ⚙️ CONFIGURATION (FINAL)
# =========================

TEMP_DIR = tempfile.gettempdir()

TARGET_W, TARGET_H = 1080, 1920
MAX_ZOOM = 1.05

FRAME_SKIP = 2
MOUTH_OPEN_THRESHOLD = 4.0
MIN_LOCK_FRAMES = 36

AUDIO_FILTERS = (
    "highpass=f=80,"
    "lowpass=f=12000,"
    "compand=0.3|0.8:1|1:-90/-60|-60/-40|-40/-30|-20/-10:6:0:-90:0.2,"
    "equalizer=f=100:t=h:w=200:g=3,"
    "equalizer=f=3500:t=h:w=300:g=2,"
    "loudnorm=I=-16:TP=-1.5:LRA=11"
)

# =========================
# 🔧 HELPERS
# =========================

def ffmpeg_escape_path(path: str) -> str:
    return path.replace("\\", "/").replace(":", "\\:")

def format_time_ass(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

# =========================
# 🎤 SUBTITLE GENERATOR
# =========================

def generate_viral_subs(audio_path, output_subs):
    print("[1/4] Transcribing & Styling Subtitles...")

    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(audio_path, word_timestamps=True)

    ass_header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Spk0,League Spartan,125,&H0000FF00,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,15,0,2,10,10,850,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    with open(output_subs, "w", encoding="utf-8") as f:
        f.write(ass_header)

        for seg in segments:
            for w in seg.words:
                if not w.word.strip():
                    continue
                start = format_time_ass(w.start)
                end = format_time_ass(w.end)
                text = w.word.strip().upper()

                anim = r"{\fscx80\fscy80\t(0,80,\fscx100\fscy100)}"
                f.write(
                    f"Dialogue: 0,{start},{end},Spk0,,0,0,0,,{anim}{text}\n"
                )

    print(f"✅ Subtitle saved: {output_subs}")

# =========================
# 🎥 CINEMA CAMERA
# =========================

class CinemaCam:
    def __init__(self, w, h):
        self.cx = w / 2
        self.cy = h / 2
        self.tx = self.cx
        self.ty = self.cy
        self.active = -1
        self.last_switch = 0
        self.frame = 0

    def update(self, target, idx):
        self.frame += 1
        if idx != self.active:
            if self.frame - self.last_switch < MIN_LOCK_FRAMES:
                return
            self.active = idx
            self.last_switch = self.frame
        self.tx, self.ty = target

    def move(self):
        dx = self.tx - self.cx
        dy = self.ty - self.cy
        dist = math.hypot(dx, dy)
        if dist < 10:
            return self.cx, self.cy
        smooth = min(0.15, max(0.03, dist / 800))
        self.cx += dx * smooth
        self.cy += dy * smooth
        return self.cx, self.cy

# =========================
# 🚀 MAIN
# =========================

def main():
    if len(sys.argv) < 4:
        print("Usage: python script.py <video.mp4> <audio.wav> <output.mp4>")
        sys.exit(1)

    input_vid = sys.argv[1]
    input_audio = sys.argv[2]
    output_vid = sys.argv[3]

    if not os.path.exists(input_vid):
        print(f"❌ Input not found: {input_vid}")
        sys.exit(1)

    base = os.path.splitext(os.path.basename(output_vid))[0]

    temp_subs = os.path.join(TEMP_DIR, f"{base}.ass")
    temp_vis = os.path.join(TEMP_DIR, f"{base}_vis.mp4")
    proxy_vid = os.path.join(TEMP_DIR, f"{base}_proxy.mp4")

    print(f"🚀 PROCESSING: {input_vid}")

    # 0. Proxy for OpenCV
    print("[0/4] Preparing proxy video...")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", input_vid, "-an",
             "-c:v", "libx264", "-preset", "ultrafast", proxy_vid],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        track_src = proxy_vid
    except subprocess.CalledProcessError:
        track_src = input_vid

    # 1. Subs (PAKAI AUDIO EXTERNAL)
    generate_viral_subs(input_audio, temp_subs)

    # 2. Smart crop
    print("[2/4] Smart tracking...")
    cap = cv2.VideoCapture(track_src)
    fw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    fh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    out = cv2.VideoWriter(
        temp_vis,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (TARGET_W, TARGET_H)
    )

    face_mesh = mp.solutions.face_mesh.FaceMesh(
        max_num_faces=5,
        refine_landmarks=True,
        min_detection_confidence=0.5
    )

    cam = CinemaCam(fw, fh)
    idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if idx % FRAME_SKIP == 0:
            small = cv2.resize(frame, (int(fw * 360 / fh), 360))
            rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            res = face_mesh.process(rgb)

            best = None
            score_max = 0
            best_i = -1

            if res.multi_face_landmarks:
                for i, lm in enumerate(res.multi_face_landmarks):
                    up = lm.landmark[13]
                    lo = lm.landmark[14]
                    mouth = abs(up.y - lo.y) * fh
                    width = abs(lm.landmark[234].x - lm.landmark[454].x)
                    score = mouth * 1.2 + width * 300
                    if score > score_max and mouth > MOUTH_OPEN_THRESHOLD:
                        nose = lm.landmark[1]
                        best = (int(nose.x * fw), int(nose.y * fh))
                        score_max = score
                        best_i = i

            if best:
                cam.update(best, best_i)

        cx, cy = cam.move()

        crop_h = int(fh / MAX_ZOOM)
        crop_w = int(crop_h * 9 / 16)
        y_adj = cy - crop_h * 0.08

        x1 = max(0, min(int(cx - crop_w / 2), fw - crop_w))
        y1 = max(0, min(int(y_adj - crop_h / 2), fh - crop_h))

        crop = frame[y1:y1+crop_h, x1:x1+crop_w]
        out.write(cv2.resize(crop, (TARGET_W, TARGET_H)))
        idx += 1

    cap.release()
    out.release()

    # 3. Final render
    print("[3/4] Final Rendering...")

    ass_path = ffmpeg_escape_path(temp_subs)

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", temp_vis,
            "-i", input_audio,
            "-filter_complex",
            f"[0:v]unsharp=5:5:1.0:5:5:0.0,ass='{ass_path}',tblend=all_mode=average,noise=alls=5:allf=t+u[v];"
            f"[1:a]{AUDIO_FILTERS}[a]",
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            output_vid
        ],
        check=True
    )

    print(f"✅ DONE: {output_vid}")

    for f in (temp_subs, temp_vis, proxy_vid):
        if os.path.exists(f):
            os.remove(f)

# =========================

if __name__ == "__main__":
    main()
