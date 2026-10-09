"""
SafeBox: Main Application Entry Point
FastAPI application orchestrating sandbox lifecycle, routers, and web interface.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import asyncio

from .core.config import settings
from .core.pool import sandbox_pool
from .queue.broker import job_broker
from .api.routes import router
from .api.websocket import ws_router

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize pre-warmed container pools & job broker
    await sandbox_pool.initialize()
    await job_broker.connect()
    
    # Start background consumer for queue
    consumer_task = asyncio.create_task(
        job_broker.start_consumer(sandbox_pool.execute_in_warm_pool)
    )
    yield
    # Teardown
    consumer_task.cancel()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="High-Throughput Sandboxed Code Execution Engine with Kernel Resource Isolation",
    lifespan=lifespan
)

# Include API routes
app.include_router(router, prefix=settings.API_PREFIX)
app.include_router(ws_router)

# Mount Static UI
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", include_in_schema=False)
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "SafeBox Code Execution Engine is running. Visit /docs for OpenAPI specs."}
