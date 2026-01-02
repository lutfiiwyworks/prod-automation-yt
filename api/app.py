import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse

from services.processor import run_processor

app = FastAPI(
    title="ProcessorProLite API",
    version="1.1.0"
)

TMP_DIR = "/tmp"


@app.post("/process")
async def process(file: UploadFile = File(...)):
    """
    Receive video as multipart/form-data (binary),
    process it, and return processed video as binary.
    """

    # --- filename from n8n binary metadata ---
    video_file = file.filename or "input.mp4"

    input_path = os.path.join(TMP_DIR, video_file)
    output_path = os.path.join(TMP_DIR, f"output_{video_file}")

    try:
        # --- save uploaded file ---
        with open(input_path, "wb") as f:
            f.write(await file.read())

        # --- run processor ---
        run_processor(input_path, output_path)

        if not os.path.exists(output_path):
            raise HTTPException(
                status_code=500,
                detail="Processing failed: output not generated"
            )

        # --- return processed video ---
        return FileResponse(
            output_path,
            media_type="video/mp4",
            filename=f"output_{video_file}"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
