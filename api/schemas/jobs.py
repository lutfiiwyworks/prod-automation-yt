from pydantic import BaseModel

class PrepareRequest(BaseModel):
    url: str
    start_detik: int
    end_detik: int


class RenderRequest(BaseModel):
    video_path: str
    absolute_start: float
    absolute_end: float


class DownloadRequest(BaseModel):
    url: str
    start_detik: int
    end_detik: int


class DownloadResponse(BaseModel):
    status: str
    video_id: str
    full_file_path: str
    start_detik: int
    end_detik: int


class ProcessRequest(BaseModel):
    input_path: str
    output_path: str
