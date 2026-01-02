from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from services.processor import process_job, read_state

app = FastAPI()

class ProcessRequest(BaseModel):
    job_id: str
    drive_url: str
    absolute_start: float
    absolute_end: float

@app.post("/process")
def process(req: ProcessRequest, bg: BackgroundTasks):
    state = read_state(req.job_id)

    if state == "running":
        return {"status": "running", "job_id": req.job_id}

    if state == "done":
        return {"status": "done", "job_id": req.job_id}

    # error / belum ada → jalan ulang
    bg.add_task(
        process_job,
        req.job_id,
        req.drive_url,
        req.absolute_start,
        req.absolute_end
    )

    return {"status": "accepted", "job_id": req.job_id}
