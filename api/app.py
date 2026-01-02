import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from services.processor import run_processor

app = FastAPI(
    title="ProcessorProLite API",
    version="1.0.0"
)

class ProcessRequest(BaseModel):
    input_path: str
    output_path: str

@app.post("/process")
def process(req: ProcessRequest):
    if not os.path.exists(req.input_path):
        raise HTTPException(status_code=400, detail="Input file not found")

    run_processor(req.input_path, req.output_path)

    return {
        "status": "ok",
        "output": req.output_path
    }
