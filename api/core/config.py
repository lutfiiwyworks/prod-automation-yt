import os

DATA_DIR = "/app/data"

INPUT_DIR = os.path.join(DATA_DIR, "input")
OUTPUT_DIR = os.path.join(DATA_DIR, "output")
TMP_DIR = os.path.join(DATA_DIR, "tmp")

for d in (INPUT_DIR, OUTPUT_DIR, TMP_DIR):
    os.makedirs(d, exist_ok=True)
