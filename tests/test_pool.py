"""
SafeBox Test Suite: Pre-Warmed Pool Architecture
Validates slot acquisition latency, concurrency capacity, and async recycling.
"""
import pytest
import asyncio
from safebox.app.core.pool import PreWarmedPoolManager
from safebox.app.core.verdict import Verdict

@pytest.mark.asyncio
async def test_pool_initialization_and_acquisition():
    pool = PreWarmedPoolManager(pool_size_per_lang=2)
    await pool.initialize()
    
    stats = pool.get_stats()
    assert stats["is_running"] is True
    assert stats["pool_capacities"]["python"] == 2
    assert stats["pool_capacities"]["cpp"] == 2

    # Acquire slot
    slot, acquire_latency_ms = await pool.acquire_slot("python")
    assert slot.language == "python"
    assert acquire_latency_ms < 50.0  # Ultra-fast acquisition <50ms

    # Run code via slot
    res = await slot.executor.execute(
        code="print('Pool Test Passed')",
        language="python"
    )
    assert res.verdict == Verdict.AC
    assert "Pool Test Passed" in res.stdout

    # Release and replenish
    await pool.release_and_replenish(slot)
    await asyncio.sleep(0.05)
    updated_stats = pool.get_stats()
    assert updated_stats["total_acquisitions"] == 1
    assert updated_stats["total_replenishments"] >= 1
