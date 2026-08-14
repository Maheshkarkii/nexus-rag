import uuid
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel

from app.services.jobs import default_job_manager

router = APIRouter(tags=["Jobs & Scalability"])


class JobStatusResponse(BaseModel):
    job_id: uuid.UUID
    project_id: uuid.UUID
    job_type: str
    status: str
    progress_percent: float
    current_stage: str
    created_at: float
    updated_at: float
    error_message: str | None = None
    retries: int
    result: Dict[str, Any] | None = None


@router.get(
    "/projects/{project_id}/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Get background job status and progress",
)
async def get_job_status(project_id: uuid.UUID, job_id: uuid.UUID):
    """Retrieve current background job execution status, progress percentage, and results."""
    job = default_job_manager.get_job(project_id, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or access denied.")
    return job.to_dict()


@router.post(
    "/projects/{project_id}/jobs/{job_id}/cancel",
    summary="Cancel a queued or running background job",
)
async def cancel_job(project_id: uuid.UUID, job_id: uuid.UUID):
    """Cancel an active background job."""
    success = default_job_manager.cancel_job(project_id, job_id)
    if not success:
        raise HTTPException(status_code=400, detail="Job could not be cancelled or does not exist.")
    return {"message": "Job cancellation requested successfully."}
