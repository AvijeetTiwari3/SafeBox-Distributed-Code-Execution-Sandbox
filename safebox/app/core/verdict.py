"""
SafeBox: Verdict Classification Engine
Analyzes execution outputs, return codes, memory spikes, and timeout interrupts
to produce standardized competitive programming verdicts.
"""
from enum import Enum
from pydantic import BaseModel, Field

class Verdict(str, Enum):
    AC = "ACCEPTED"
    WA = "WRONG_ANSWER"
    TLE = "TIME_LIMIT_EXCEEDED"
    MLE = "MEMORY_LIMIT_EXCEEDED"
    RE = "RUNTIME_ERROR"
    CE = "COMPILATION_ERROR"
    SE = "SECURITY_VIOLATION"

class ExecutionResult(BaseModel):
    verdict: Verdict
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    execution_time_ms: float = 0.0
    compilation_time_ms: float = 0.0
    peak_memory_mb: float = 0.0
    passed_tests: int = 0
    total_tests: int = 0
    diagnostics: str = ""
    sandbox_backend: str = "Native OS Kernel"

def evaluate_verdict(
    exit_code: int,
    stdout: str,
    stderr: str,
    timed_out: bool,
    oom_killed: bool,
    security_violation: str | None,
    expected_output: str | None = None
) -> tuple[Verdict, str]:
    """
    Classifies the raw execution outcome into a formal Verdict.
    """
    if security_violation:
        return Verdict.SE, f"Sandbox security guard triggered: {security_violation}"

    if timed_out:
        return Verdict.TLE, "Execution exceeded maximum configured time limit (TLE)"

    if oom_killed:
        return Verdict.MLE, "Memory limit exceeded; process terminated by kernel ceiling (MLE)"

    # Windows status codes or Linux signals for crash / segfault
    # 0xC0000005 = STATUS_ACCESS_VIOLATION (Segfault)
    # 0xC0000017 = STATUS_NO_MEMORY
    # -9 = SIGKILL (often OOM or Timeout)
    # -11 = SIGSEGV
    if exit_code in (-9, 137) and not timed_out:
        return Verdict.MLE, "Process terminated by kernel OOM kill signal"

    if exit_code in (0xC0000005, -11):
        return Verdict.RE, "Segmentation fault / memory access violation (SIGSEGV)"

    if exit_code != 0:
        err_msg = stderr.strip() if stderr.strip() else f"Process exited with non-zero status code: {exit_code}"
        return Verdict.RE, err_msg

    if expected_output is not None:
        actual_cleaned = stdout.strip().replace("\r\n", "\n")
        expected_cleaned = expected_output.strip().replace("\r\n", "\n")
        if actual_cleaned == expected_cleaned:
            return Verdict.AC, "Test cases passed successfully."
        else:
            return Verdict.WA, f"Output mismatch. Expected:\n{expected_cleaned[:200]}\nGot:\n{actual_cleaned[:200]}"

    return Verdict.AC, "Execution completed successfully with exit code 0."
