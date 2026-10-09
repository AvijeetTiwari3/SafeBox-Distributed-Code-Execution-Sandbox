"""
SafeBox: Linux cgroups v2 Kernel Sandboxing
Implements resource isolation and accounting via unified Linux cgroups v2 filesystem.
"""
from pathlib import Path
import os
import sys
import logging

logger = logging.getLogger("safebox.sandbox.linux")

IS_LINUX = sys.platform.startswith("linux")

class LinuxCgroupV2Sandbox:
    """
    Manages a dedicated cgroup v2 subtree under /sys/fs/cgroup/safebox/
    """
    CGROUP_ROOT = Path("/sys/fs/cgroup/safebox")

    def __init__(self, job_id: str, memory_limit_mb: int = 128, cpu_quota_pct: int = 50, max_pids: int = 16):
        self.job_id = job_id
        self.cgroup_path = self.CGROUP_ROOT / job_id
        self.memory_limit_bytes = memory_limit_mb * 1024 * 1024
        self.cpu_quota_pct = cpu_quota_pct
        self.max_pids = max_pids
        self.active = False

        if IS_LINUX:
            self._setup_cgroup()

    def _setup_cgroup(self):
        try:
            self.cgroup_path.mkdir(parents=True, exist_ok=True)
            
            # Configure memory cap (memory.max) & disable swap
            mem_max = self.cgroup_path / "memory.max"
            if mem_max.exists():
                mem_max.write_text(str(self.memory_limit_bytes))
            
            swap_max = self.cgroup_path / "memory.swap.max"
            if swap_max.exists():
                swap_max.write_text("0")

            # Configure PID limit (pids.max) for fork-bomb deterrence
            pids_max = self.cgroup_path / "pids.max"
            if pids_max.exists():
                pids_max.write_text(str(self.max_pids))

            # Configure CPU quota (cpu.max) -> "50000 100000" for 50% core
            cpu_max = self.cgroup_path / "cpu.max"
            if cpu_max.exists():
                quota = int(self.cpu_quota_pct * 1000)
                cpu_max.write_text(f"{quota} 100000")

            self.active = True
        except Exception as e:
            logger.warning(f"Could not configure Linux cgroups v2: {e}")
            self.active = False

    def attach_pid(self, pid: int) -> bool:
        if not self.active or not IS_LINUX:
            return False
        try:
            procs_file = self.cgroup_path / "cgroup.procs"
            procs_file.write_text(str(pid))
            return True
        except Exception as e:
            logger.error(f"Failed to attach pid {pid} to cgroup: {e}")
            return False

    def check_oom(self) -> bool:
        if not self.active or not IS_LINUX:
            return False
        try:
            events_file = self.cgroup_path / "memory.events"
            if events_file.exists():
                content = events_file.read_text()
                for line in content.splitlines():
                    if line.startswith("oom_kill") and int(line.split()[1]) > 0:
                        return True
        except Exception:
            pass
        return False

    def teardown(self):
        if self.active and IS_LINUX:
            try:
                # Kill remaining processes
                kill_file = self.cgroup_path / "cgroup.kill"
                if kill_file.exists():
                    kill_file.write_text("1")
                self.cgroup_path.rmdir()
            except Exception:
                pass
            self.active = False
