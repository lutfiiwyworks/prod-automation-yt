from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel

from services.processor import process_job, read_state

app = FastAPI()


class ProcessRequest(BaseModel):
    job_id: str
    video_url: str
    audio_url: str
    absolute_start: float
    absolute_end: float



@app.post("/process")
def process(req: ProcessRequest):
  result = process_job(
    req.job_id,
    req.video_url,
    req.audio_url,
    req.absolute_start,
    req.absolute_end,
)


    # LANGSUNG RETURN HASIL
    return {
        "job_id": req.job_id,
        "drive_file_id": result["file_id"],
        "drive_link": result["webViewLink"],
    }

