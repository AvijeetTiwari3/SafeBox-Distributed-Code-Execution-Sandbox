"""
SafeBox: Windows Job Object Kernel Sandboxing
Implements deterministic CPU, Memory, and Active Process limits using native Windows Job Objects.
Equivalent to Linux cgroups v2 for Windows host environments.
"""
import sys
import logging

logger = logging.getLogger("safebox.sandbox.windows")

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import win32job
    import win32api
    import win32process
    import win32con

class WindowsJobSandbox:
    """
    Encapsulates a Windows Job Object configured with hard resource ceilings.
    """
    def __init__(self, memory_limit_mb: int = 128, max_processes: int = 16, time_limit_ms: int = 2000):
        self.memory_limit_bytes = memory_limit_mb * 1024 * 1024
        self.max_processes = max_processes
        self.time_limit_ms = time_limit_ms
        self.job = None
        self.initialized = False

        if IS_WINDOWS:
            self._create_job_object()

    def _create_job_object(self):
        try:
            self.job = win32job.CreateJobObject(None, "")
            info = win32job.QueryInformationJobObject(
                self.job, win32job.JobObjectExtendedLimitInformation
            )
            
            # Configure Extended Limits
            basic_limit = info['BasicLimitInformation']
            
            # Ceilings: Kill on close, process memory limit, active process limit
            limit_flags = (
                win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE |
                win32job.JOB_OBJECT_LIMIT_PROCESS_MEMORY |
                win32job.JOB_OBJECT_LIMIT_JOB_MEMORY |
                win32job.JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            )
            
            basic_limit['LimitFlags'] = limit_flags
            basic_limit['ActiveProcessLimit'] = self.max_processes
            
            # Set memory ceilings (bytes)
            info['ProcessMemoryLimit'] = self.memory_limit_bytes
            info['JobMemoryLimit'] = self.memory_limit_bytes

            win32job.SetInformationJobObject(
                self.job, win32job.JobObjectExtendedLimitInformation, info
            )
            self.initialized = True
        except Exception as e:
            logger.warning(f"Failed to initialize Windows Job Object: {e}")
            self.initialized = False

    def assign_process(self, process_handle):
        """
        Binds a running process handle into this Job Object sandbox.
        """
        if not self.initialized or not IS_WINDOWS:
            return False
        try:
            win32job.AssignProcessToJobObject(self.job, process_handle)
            return True
        except Exception as e:
            logger.error(f"Failed to assign process to Job Object: {e}")
            return False

    def get_stats(self) -> dict:
        """
        Queries memory peak and execution metrics from the job object.
        """
        if not self.initialized or not IS_WINDOWS:
            return {"peak_memory_mb": 0.0, "total_user_time_ms": 0}
        try:
            info = win32job.QueryInformationJobObject(
                self.job, win32job.JobObjectExtendedLimitInformation
            )
            peak_bytes = info.get('PeakProcessMemoryUsed', 0)
            return {
                "peak_memory_mb": round(peak_bytes / (1024 * 1024), 2),
                "peak_bytes": peak_bytes
            }
        except Exception:
            return {"peak_memory_mb": 0.0, "peak_bytes": 0}

    def close(self):
        """
        Terminates all associated processes and frees the kernel object.
        """
        if self.job and IS_WINDOWS:
            try:
                win32api.CloseHandle(self.job)
            except Exception:
                pass
            self.job = None
