import subprocess
import os
import sys

SCRIPT_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "processorprolite-v1.py")
)

def run_processor(input_path: str, output_path: str):
    subprocess.run(
        [sys.executable, SCRIPT_PATH, input_path, output_path],
        check=True
    )
