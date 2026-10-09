"""
SafeBox: REST API Endpoints
Provides endpoints for synchronous execution, asynchronous batch submissions,
runtime statistics, and Prometheus telemetry.
"""
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
from typing import Optional

from ..core.config import settings, SUPPORTED_LANGUAGES, ResourceLimits
from ..core.pool import sandbox_pool
from ..core.verdict import ExecutionResult
from ..queue.broker import job_broker
from ..telemetry.metrics import metrics

router = APIRouter()

class ExecuteRequest(BaseModel):
    code: str = Field(..., max_length=settings.MAX_PAYLOAD_CODE_BYTES)
    language: str
    stdin_data: str = ""
    expected_output: Optional[str] = None
    time_limit_ms: Optional[int] = None
    memory_limit_mb: Optional[int] = None

class SubmitResponse(BaseModel):
    job_id: str
    status: str
    message: str

@router.get("/languages")
async def list_languages():
    """Returns available compiler & interpreter runtimes."""
    return {
        lang_id: {
            "name": cfg.name,
            "extension": cfg.extension,
            "compiled": cfg.compiled,
            "template": cfg.default_template
        }
        for lang_id, cfg in SUPPORTED_LANGUAGES.items()
    }

@router.post("/execute", response_model=ExecutionResult)
async def execute_code(req: ExecuteRequest):
    """
    Synchronously runs code through the pre-warmed sandbox pool with sub-100ms latency.
    """
    lang = req.language.lower()
    if lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Unsupported language '{req.language}'.")

    result = await sandbox_pool.execute_in_warm_pool(
        code=req.code,
        language=lang,
        stdin_data=req.stdin_data,
        expected_output=req.expected_output
    )

    # Record telemetry
    metrics.record_execution(
        verdict=result.verdict.value,
        language=lang,
        exec_time_ms=result.execution_time_ms,
        peak_memory_mb=result.peak_memory_mb
    )

    return result

@router.post("/submit", response_model=SubmitResponse)
async def submit_job(req: ExecuteRequest):
    """
    Asynchronously enqueues a job into the distributed stream broker.
    """
    lang = req.language.lower()
    if lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Unsupported language '{req.language}'.")

    job_id = await job_broker.enqueue(
        code=req.code,
        language=lang,
        stdin_data=req.stdin_data,
        expected_output=req.expected_output
    )
    return SubmitResponse(
        job_id=job_id,
        status="QUEUED",
        message="Job successfully dispatched to broker queue."
    )

@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Queries execution state of an asynchronous job."""
    job = job_broker.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job ID not found.")
    return {
        "job_id": job.job_id,
        "status": job.status,
        "result": job.result
    }

@router.get("/pool/stats")
async def get_pool_stats():
    """Returns real-time capacity and utilization of the pre-warmed container pool."""
    return sandbox_pool.get_stats()

@router.get("/metrics/summary")
async def get_metrics_summary():
    """Returns JSON telemetry dashboard metrics."""
    return metrics.get_summary()

@router.get("/metrics", response_class=Response)
async def get_prometheus_metrics():
    """Exposes Prometheus standard text exposition format for scraping."""
    content = metrics.generate_prometheus_metrics()
    return Response(content=content, media_type="text/plain; version=0.0.4")
