import logging
import uuid
import time
import asyncio
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.core.config import get_settings

logger = logging.getLogger("ai_research_assistant.services.jobs")


class Job:
    """Represents a background processing job lifecycle."""

    def __init__(self, project_id: uuid.UUID, job_type: str) -> None:
        self.id: uuid.UUID = uuid.uuid4()
        self.project_id: uuid.UUID = project_id
        self.job_type: str = job_type
        self.status: str = "queued"  # queued, running, completed, failed, cancelled
        self.progress_percent: float = 0.0
        self.current_stage: str = "Queued"
        self.created_at: float = time.time()
        self.updated_at: float = time.time()
        self.error_message: Optional[str] = None
        self.retries: int = 0
        self.result: Optional[Dict[str, Any]] = None

    def update_progress(self, percent: float, stage: str) -> None:
        """Update job progress percentage and current stage label."""
        self.progress_percent = round(max(0.0, min(100.0, percent)), 2)
        self.current_stage = stage
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": str(self.id),
            "project_id": str(self.project_id),
            "job_type": self.job_type,
            "status": self.status,
            "progress_percent": self.progress_percent,
            "current_stage": self.current_stage,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error_message": self.error_message,
            "retries": self.retries,
            "result": self.result,
        }


class BackgroundJobManager:
    """In-memory task manager for async background job execution, retries, and progress tracking."""

    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._semaphore: Optional[asyncio.Semaphore] = None

    def _ensure_worker(self) -> None:
        settings = get_settings()
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_JOBS)
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop())

    def submit_job(self, project_id: uuid.UUID, job_type: str, task_func: Callable, *args, **kwargs) -> Job:
        """Submit a background job for async execution."""
        job = Job(project_id=project_id, job_type=job_type)
        self._jobs[str(job.id)] = job
        self._ensure_worker()
        self._queue.put_nowait((job, task_func, args, kwargs))
        logger.info(f"Submitted background job {job.id} (type: {job_type}) for project {project_id}")
        return job

    def get_job(self, project_id: uuid.UUID, job_id: uuid.UUID) -> Optional[Job]:
        """Retrieve job record with project-level authorization check."""
        job = self._jobs.get(str(job_id))
        if job and job.project_id == project_id:
            return job
        return None

    def cancel_job(self, project_id: uuid.UUID, job_id: uuid.UUID) -> bool:
        """Cancel a queued or running job."""
        job = self.get_job(project_id, job_id)
        if not job:
            return False
        if job.status in ("queued", "running"):
            job.status = "cancelled"
            job.update_progress(job.progress_percent, "Cancelled by user")
            logger.info(f"Job {job_id} was cancelled by user.")
            return True
        return False

    async def _worker_loop(self) -> None:
        """Worker loop processing background jobs from queue with concurrency semaphores and retries."""
        settings = get_settings()
        while True:
            try:
                job, task_func, args, kwargs = await self._queue.get()
                if job.status == "cancelled":
                    self._queue.task_done()
                    continue

                async with self._semaphore:
                    job.status = "running"
                    job.update_progress(5.0, "Starting processing")

                    success = False
                    while job.retries <= settings.MAX_JOB_RETRIES and not success:
                        if job.status == "cancelled":
                            break

                        try:
                            # Execute job callback
                            res = await task_func(job, *args, **kwargs)
                            if job.status != "cancelled":
                                job.status = "completed"
                                job.update_progress(100.0, "Processing completed")
                                job.result = res if isinstance(res, dict) else {"status": "success"}
                            success = True
                        except Exception as e:
                            job.retries += 1
                            logger.error(f"Job {job.id} attempt {job.retries} failed: {e}")
                            if job.retries > settings.MAX_JOB_RETRIES:
                                job.status = "failed"
                                job.error_message = str(e)
                                job.update_progress(job.progress_percent, f"Failed: {e}")
                            else:
                                # Backoff retry
                                await asyncio.sleep(0.5 * job.retries)

                self._queue.task_done()
            except Exception as loop_err:
                logger.error(f"Worker loop error: {loop_err}")
                await asyncio.sleep(1.0)


# Singleton job manager instance
default_job_manager = BackgroundJobManager()
