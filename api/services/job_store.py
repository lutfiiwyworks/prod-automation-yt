import threading
import time

JOB_STORE = {}
LOCK = threading.Lock()

def set_job(job_id, data):
    with LOCK:
        JOB_STORE[job_id] = {
            **JOB_STORE.get(job_id, {}),
            **data,
            "updated_at": time.time()
        }

def get_job(job_id):
    with LOCK:
        return JOB_STORE.get(job_id)
