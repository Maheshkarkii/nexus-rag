import uuid
import asyncio
import pytest

from app.services.jobs import BackgroundJobManager, Job


@pytest.mark.asyncio
async def test_job_creation_and_completion() -> None:
    mgr = BackgroundJobManager()
    p_id = uuid.uuid4()

    async def sample_task(job: Job):
        job.update_progress(50.0, "Halfway done")
        await asyncio.sleep(0.05)
        return {"processed": 42}

    job = mgr.submit_job(p_id, "test_job", sample_task)
    assert job.status in ("queued", "running")

    # Wait for completion
    for _ in range(20):
        if job.status == "completed":
            break
        await asyncio.sleep(0.05)

    assert job.status == "completed"
    assert job.progress_percent == 100.0
    assert job.result == {"processed": 42}


@pytest.mark.asyncio
async def test_job_cancellation() -> None:
    mgr = BackgroundJobManager()
    p_id = uuid.uuid4()

    async def long_task(job: Job):
        await asyncio.sleep(1.0)
        return {"done": True}

    job = mgr.submit_job(p_id, "long_job", long_task)
    cancelled = mgr.cancel_job(p_id, job.id)

    assert cancelled is True
    assert job.status == "cancelled"


@pytest.mark.asyncio
async def test_job_authorization_isolation() -> None:
    mgr = BackgroundJobManager()
    p1 = uuid.uuid4()
    p2 = uuid.uuid4()

    async def dummy_task(job: Job):
        return {}

    job = mgr.submit_job(p1, "dummy", dummy_task)
    
    # Authorized lookup
    res_auth = mgr.get_job(p1, job.id)
    # Unauthorized lookup (Project 2)
    res_unauth = mgr.get_job(p2, job.id)

    assert res_auth is not None
    assert res_unauth is None


@pytest.mark.asyncio
async def test_job_retry_on_failure() -> None:
    mgr = BackgroundJobManager()
    p_id = uuid.uuid4()
    attempts = 0

    async def failing_task(job: Job):
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise ValueError("Transient error")
        return {"retry_success": True}

    job = mgr.submit_job(p_id, "retry_job", failing_task)

    for _ in range(30):
        if job.status in ("completed", "failed"):
            break
        await asyncio.sleep(0.05)

    assert job.status == "completed"
    assert job.retries == 1
    assert job.result == {"retry_success": True}
