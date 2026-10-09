"""
SafeBox: Pre-Warmed Sandbox Pool Manager
Maintains standby sandboxes per language runtime to drop P95 execution start latency from ~500ms to <10ms.
"""
import asyncio
import time
import logging
from dataclasses import dataclass
from typing import Dict, List
from .config import settings, ResourceLimits
from .executor import SandboxedExecutor
from .verdict import ExecutionResult

logger = logging.getLogger("safebox.pool")

@dataclass
class WarmSandboxSlot:
    slot_id: str
    language: str
    created_at: float
    executor: SandboxedExecutor

class PreWarmedPoolManager:
    """
    Asynchronous FIFO pool of pre-warmed sandbox executors.
    """
    def __init__(self, pool_size_per_lang: int = 3):
        self.pool_size_per_lang = pool_size_per_lang
        self.pools: Dict[str, asyncio.Queue[WarmSandboxSlot]] = {
            "python": asyncio.Queue(maxsize=pool_size_per_lang * 2),
            "cpp": asyncio.Queue(maxsize=pool_size_per_lang * 2),
            "javascript": asyncio.Queue(maxsize=pool_size_per_lang * 2),
        }
        self.total_acquisitions = 0
        self.total_replenishments = 0
        self.is_running = False

    async def initialize(self):
        """
        Pre-populates each language queue with warm sandbox slots.
        """
        self.is_running = True
        for lang in self.pools.keys():
            for i in range(self.pool_size_per_lang):
                slot = self._create_slot(lang, f"init_{i}")
                await self.pools[lang].put(slot)
                self.total_replenishments += 1
        logger.info(f"Pre-warmed Sandbox Pool initialized with {self.pool_size_per_lang} slots per language.")

    def _create_slot(self, language: str, tag: str) -> WarmSandboxSlot:
        return WarmSandboxSlot(
            slot_id=f"{language}_{tag}_{int(time.time() * 1000)}",
            language=language,
            created_at=time.perf_counter(),
            executor=SandboxedExecutor()
        )

    async def acquire_slot(self, language: str) -> tuple[WarmSandboxSlot, float]:
        """
        Retrieves a pre-warmed sandbox slot. Measures acquisition latency.
        """
        start_t = time.perf_counter()
        lang = language.lower()
        if lang not in self.pools:
            slot = self._create_slot(lang, "fallback")
            acquire_ms = (time.perf_counter() - start_t) * 1000.0
            return slot, acquire_ms

        try:
            # Try to grab an idle pre-warmed slot immediately
            slot = self.pools[lang].get_nowait()
        except asyncio.QueueEmpty:
            # If all pre-warmed slots are occupied under heavy load, spawn on demand
            slot = self._create_slot(lang, "burst")

        acquire_ms = (time.perf_counter() - start_t) * 1000.0
        self.total_acquisitions += 1
        return slot, acquire_ms

    async def release_and_replenish(self, slot: WarmSandboxSlot):
        """
        Recycles the slot asynchronously so the caller is never blocked.
        """
        lang = slot.language
        if lang in self.pools:
            new_slot = self._create_slot(lang, "replenished")
            try:
                self.pools[lang].put_nowait(new_slot)
                self.total_replenishments += 1
            except asyncio.QueueFull:
                pass

    async def execute_in_warm_pool(
        self,
        code: str,
        language: str,
        stdin_data: str = "",
        expected_output: str | None = None
    ) -> ExecutionResult:
        slot, acquire_latency_ms = await self.acquire_slot(language)
        try:
            result = await slot.executor.execute(
                code=code,
                language=language,
                stdin_data=stdin_data,
                expected_output=expected_output
            )
            return result
        finally:
            asyncio.create_task(self.release_and_replenish(slot))

    def get_stats(self) -> dict:
        return {
            "is_running": self.is_running,
            "pool_capacities": {lang: q.qsize() for lang, q in self.pools.items()},
            "total_acquisitions": self.total_acquisitions,
            "total_replenishments": self.total_replenishments
        }

# Global pool singleton
sandbox_pool = PreWarmedPoolManager(pool_size_per_lang=settings.WARM_POOL_SIZE_PER_LANG)
