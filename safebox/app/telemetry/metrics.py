"""
SafeBox: Telemetry & Prometheus Metrics Exporter
Tracks execution latencies, verdict distributions, memory allocations, and pool utilization.
"""
import time
from collections import defaultdict
from typing import Dict, List

class MetricsCollector:
    def __init__(self):
        self.verdict_counts: Dict[str, int] = defaultdict(int)
        self.language_counts: Dict[str, int] = defaultdict(int)
        self.execution_times_ms: List[float] = []
        self.peak_memories_mb: List[float] = []
        self.start_timestamp = time.time()

    def record_execution(self, verdict: str, language: str, exec_time_ms: float, peak_memory_mb: float):
        self.verdict_counts[verdict] += 1
        self.language_counts[language] += 1
        self.execution_times_ms.append(exec_time_ms)
        self.peak_memories_mb.append(peak_memory_mb)

        # Keep rolling window of last 1000 executions for percentile calculations
        if len(self.execution_times_ms) > 1000:
            self.execution_times_ms.pop(0)
        if len(self.peak_memories_mb) > 1000:
            self.peak_memories_mb.pop(0)

    def get_summary(self) -> dict:
        total = sum(self.verdict_counts.values())
        latencies = sorted(self.execution_times_ms) if self.execution_times_ms else [0.0]
        
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]

        return {
            "uptime_seconds": round(time.time() - self.start_timestamp, 1),
            "total_executions": total,
            "verdicts": dict(self.verdict_counts),
            "languages": dict(self.language_counts),
            "latency_p50_ms": round(p50, 2),
            "latency_p95_ms": round(p95, 2),
            "latency_p99_ms": round(p99, 2),
            "avg_peak_memory_mb": round(sum(self.peak_memories_mb) / max(len(self.peak_memories_mb), 1), 2)
        }

    def generate_prometheus_metrics(self) -> str:
        lines = []
        lines.append("# HELP safebox_executions_total Total executions partitioned by verdict")
        lines.append("# TYPE safebox_executions_total counter")
        for verdict, count in self.verdict_counts.items():
            lines.append(f'safebox_executions_total{{verdict="{verdict}"}} {count}')

        lines.append("# HELP safebox_language_requests_total Total submissions partitioned by language")
        lines.append("# TYPE safebox_language_requests_total counter")
        for lang, count in self.language_counts.items():
            lines.append(f'safebox_language_requests_total{{language="{lang}"}} {count}')

        summary = self.get_summary()
        lines.append("# HELP safebox_execution_duration_p95_ms 95th percentile execution latency in milliseconds")
        lines.append("# TYPE safebox_execution_duration_p95_ms gauge")
        lines.append(f"safebox_execution_duration_p95_ms {summary['latency_p95_ms']}")

        lines.append("# HELP safebox_uptime_seconds Process uptime in seconds")
        lines.append("# TYPE safebox_uptime_seconds counter")
        lines.append(f"safebox_uptime_seconds {summary['uptime_seconds']}")

        return "\n".join(lines) + "\n"

metrics = MetricsCollector()
