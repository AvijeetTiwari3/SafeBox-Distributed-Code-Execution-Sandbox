"""
SafeBox: WebSocket Real-Time Execution Stream
Enables live stdout/stderr chunk streaming and telemetry for interactive IDE sessions.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import asyncio
import time
from ..core.pool import sandbox_pool
from ..core.config import SUPPORTED_LANGUAGES
from ..telemetry.metrics import metrics

ws_router = APIRouter()

@ws_router.websocket("/ws/execute")
async def websocket_execute(websocket: WebSocket):
    await websocket.accept()
    try:
        data = await websocket.receive_text()
        req = json.loads(data)

        code = req.get("code", "")
        language = req.get("language", "python").lower()
        stdin_data = req.get("stdin_data", "")
        expected_output = req.get("expected_output", None)

        if language not in SUPPORTED_LANGUAGES:
            await websocket.send_json({
                "event": "ERROR",
                "message": f"Language '{language}' is not supported."
            })
            await websocket.close()
            return

        # Notification: Job dispatched
        await websocket.send_json({
            "event": "DISPATCHED",
            "timestamp": time.time(),
            "message": "Assigned to pre-warmed sandbox slot."
        })

        # Callback for stream chunks
        loop = asyncio.get_running_loop()
        def on_stream(stream_type: str, chunk: str):
            asyncio.run_coroutine_threadsafe(
                websocket.send_json({
                    "event": "CHUNK",
                    "stream": stream_type,
                    "data": chunk
                }),
                loop
            )

        # Execute
        result = await sandbox_pool.execute_in_warm_pool(
            code=code,
            language=language,
            stdin_data=stdin_data,
            expected_output=expected_output
        )

        # Record metrics
        metrics.record_execution(
            verdict=result.verdict.value,
            language=language,
            exec_time_ms=result.execution_time_ms,
            peak_memory_mb=result.peak_memory_mb
        )

        await websocket.send_json({
            "event": "FINISHED",
            "result": result.model_dump()
        })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({
                "event": "ERROR",
                "message": str(e)
            })
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
