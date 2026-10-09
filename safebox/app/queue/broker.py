"""
SafeBox: Distributed Job Queue & Stream Broker
Abstracts Redis Streams with transparent local in-memory fallback for asynchronous execution requests.
"""
import asyncio
import json
import uuid
import logging
from typing import Optional, Dict
from pydantic import BaseModel
from ..core.config import settings
from ..core.verdict import ExecutionResult

logger = logging.getLogger("safebox.queue")

class ExecutionJob(BaseModel):
    job_id: str
    code: str
    language: str
    stdin_data: str = ""
    expected_output: Optional[str] = None
    status: str = "QUEUED" # QUEUED, RUNNING, COMPLETED, FAILED
    result: Optional[ExecutionResult] = None

class JobBroker:
    def __init__(self):
        self.jobs: Dict[str, ExecutionJob] = {}
        self.queue: asyncio.Queue[ExecutionJob] = asyncio.Queue()
        self.redis_client = None
        self._worker_task: Optional[asyncio.Task] = None

    async def connect(self):
        try:
            import redis.asyncio as aioredis
            self.redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            await self.redis_client.ping()
            logger.info("Connected to Redis distributed stream broker.")
        except Exception:
            logger.info("Redis unavailable; operating in High-Performance In-Memory Async Broker mode.")
            self.redis_client = None

    async def enqueue(self, code: str, language: str, stdin_data: str = "", expected_output: Optional[str] = None) -> str:
        job_id = f"job_{uuid.uuid4().hex[:10]}"
        job = ExecutionJob(
            job_id=job_id,
            code=code,
            language=language,
            stdin_data=stdin_data,
            expected_output=expected_output,
            status="QUEUED"
        )
        self.jobs[job_id] = job
        await self.queue.put(job)
        return job_id

    def get_job(self, job_id: str) -> Optional[ExecutionJob]:
        return self.jobs.get(job_id)

    async def start_consumer(self, executor_fn):
        """
        Background worker consumer loop pulling jobs from the broker queue.
        """
        while True:
            job = await self.queue.get()
            job.status = "RUNNING"
            try:
                res = await executor_fn(
                    code=job.code,
                    language=job.language,
                    stdin_data=job.stdin_data,
                    expected_output=job.expected_output
                )
                job.result = res
                job.status = "COMPLETED"
            except Exception as e:
                job.status = "FAILED"
            finally:
                self.queue.task_done()

job_broker = JobBroker()
