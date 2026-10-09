"""
SafeBox: Low-Level Isolated Process Executor
Executes untrusted processes with kernel resource fences, streaming buffers, and watchdog supervisors.
"""
import subprocess
import time
import uuid
import sys
import os
import shutil
from pathlib import Path
from typing import AsyncGenerator, Callable
import asyncio

from .config import settings, ResourceLimits, SUPPORTED_LANGUAGES, SANDBOX_TEMP_DIR
from .job_windows import WindowsJobSandbox, IS_WINDOWS
from .cgroup_linux import LinuxCgroupV2Sandbox, IS_LINUX
from .verdict import ExecutionResult, Verdict, evaluate_verdict
from .compiler import compile_source
from .security import audit_code

class SandboxedExecutor:
    """
    Supervises execution of untrusted scripts inside operating system fences.
    """
    def __init__(self, limits: ResourceLimits | None = None):
        self.limits = limits or settings.DEFAULT_LIMITS

    async def execute(
        self,
        code: str,
        language: str,
        stdin_data: str = "",
        expected_output: str | None = None,
        stream_callback: Callable[[str, str], None] | None = None
    ) -> ExecutionResult:
        language = language.lower()
        if language not in SUPPORTED_LANGUAGES:
            return ExecutionResult(
                verdict=Verdict.RE,
                diagnostics=f"Unsupported language runtime: '{language}'"
            )

        lang_cfg = SUPPORTED_LANGUAGES[language]

        # Step 1: Static Security Audit (Defense-in-Depth)
        if settings.ENABLE_STATIC_ANALYSIS:
            security_check = audit_code(code, language)
            if not security_check.is_safe:
                return ExecutionResult(
                    verdict=Verdict.SE,
                    diagnostics=f"Security Policy Rejection: {security_check.violation_reason} [{security_check.rule_triggered}]",
                    sandbox_backend="Static AST & Regex Policy Filter"
                )

        # Step 2: Workspace Provisioning
        job_id = f"safebox_{uuid.uuid4().hex[:12]}"
        workspace_dir = SANDBOX_TEMP_DIR / job_id
        workspace_dir.mkdir(parents=True, exist_ok=True)

        source_file = workspace_dir / f"solution{lang_cfg.extension}"
        source_file.write_text(code, encoding="utf-8")

        compilation_time_ms = 0.0
        binary_or_script = source_file

        # Step 3: Compilation (if applicable)
        if lang_cfg.compiled:
            comp_res = compile_source(source_file, language)
            compilation_time_ms = comp_res.duration_ms
            if not comp_res.success:
                shutil.rmtree(workspace_dir, ignore_errors=True)
                return ExecutionResult(
                    verdict=Verdict.CE,
                    stderr=comp_res.error_msg,
                    compilation_time_ms=compilation_time_ms,
                    diagnostics="Code compilation failed."
                )
            binary_or_script = comp_res.binary_path

        # Step 4: Construct Command
        cmd = []
        if lang_cfg.compiled:
            cmd = [str(binary_or_script)]
        else:
            for token in lang_cfg.run_cmd:
                formatted = token.replace("{file}", str(binary_or_script))
                cmd.append(formatted)

        # Step 5: Sandbox Boundary Preparation
        job_sandbox = None
        cgroup_sandbox = None
        sandbox_backend = "Isolated Process Subsystem"

        if IS_WINDOWS:
            job_sandbox = WindowsJobSandbox(
                memory_limit_mb=self.limits.memory_limit_mb,
                max_processes=self.limits.max_processes,
                time_limit_ms=self.limits.time_limit_ms
            )
            sandbox_backend = "Windows Job Object (Kernel Extended Limits)"
        elif IS_LINUX:
            cgroup_sandbox = LinuxCgroupV2Sandbox(
                job_id=job_id,
                memory_limit_mb=self.limits.memory_limit_mb,
                cpu_quota_pct=int(self.limits.cpu_cores * 100),
                max_pids=self.limits.max_processes
            )
            sandbox_backend = "Linux cgroups v2 + Namespace Isolation"

        # Step 6: Process Spawning & Watchdog
        timed_out = False
        oom_killed = False
        stdout_acc = []
        stderr_acc = []
        exit_code = 0
        peak_memory_mb = 0.0

        start_time = time.perf_counter()
        
        try:
            # We create process with pipes
            creation_flags = 0
            if IS_WINDOWS:
                # CREATE_BREAKAWAY_FROM_JOB if needed or CREATE_SUSPENDED
                # In standard Python, subprocess.Popen works cleanly
                creation_flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0

            proc = subprocess.Popen(
                cmd,
                cwd=workspace_dir,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creation_flags
            )

            # Assign to OS kernel sandbox immediately
            if job_sandbox:
                job_sandbox.assign_process(proc._handle)
            if cgroup_sandbox:
                cgroup_sandbox.attach_pid(proc.pid)

            # Send stdin data and communicate with timeout
            stdin_bytes = stdin_data.encode("utf-8") if stdin_data else None
            timeout_sec = self.limits.time_limit_ms / 1000.0

            try:
                raw_stdout, raw_stderr = proc.communicate(input=stdin_bytes, timeout=timeout_sec)
                exit_code = proc.returncode

                # Decode and truncate to prevent memory explosion
                stdout_str = raw_stdout.decode("utf-8", errors="replace")[:self.limits.max_output_bytes]
                stderr_str = raw_stderr.decode("utf-8", errors="replace")[:self.limits.max_output_bytes]
                stdout_acc.append(stdout_str)
                stderr_acc.append(stderr_str)

                if stream_callback:
                    stream_callback("stdout", stdout_str)
                    if stderr_str:
                        stream_callback("stderr", stderr_str)

            except subprocess.TimeoutExpired:
                timed_out = True
                proc.kill()
                proc.poll()
                stdout_acc.append("[Execution Killed by Watchdog Timer: Time Limit Exceeded]")

        except Exception as e:
            stderr_acc.append(f"Runtime execution failure: {str(e)}")
            exit_code = -1

        finally:
            exec_duration_ms = (time.perf_counter() - start_time) * 1000.0

            # Collect metrics from sandbox before teardown
            if job_sandbox:
                stats = job_sandbox.get_stats()
                peak_memory_mb = stats.get("peak_memory_mb", 0.0)
                # If memory spiked over 95% of limit or status quota exceeded
                if peak_memory_mb >= (self.limits.memory_limit_mb * 0.95):
                    oom_killed = True
                job_sandbox.close()

            if cgroup_sandbox:
                if cgroup_sandbox.check_oom():
                    oom_killed = True
                cgroup_sandbox.teardown()

            # Workspace teardown
            shutil.rmtree(workspace_dir, ignore_errors=True)

        full_stdout = "".join(stdout_acc)
        full_stderr = "".join(stderr_acc)

        verdict, diagnostics = evaluate_verdict(
            exit_code=exit_code,
            stdout=full_stdout,
            stderr=full_stderr,
            timed_out=timed_out,
            oom_killed=oom_killed,
            security_violation=None,
            expected_output=expected_output
        )

        return ExecutionResult(
            verdict=verdict,
            exit_code=exit_code,
            stdout=full_stdout,
            stderr=full_stderr,
            execution_time_ms=round(exec_duration_ms, 2),
            compilation_time_ms=round(compilation_time_ms, 2),
            peak_memory_mb=round(peak_memory_mb, 2),
            passed_tests=1 if verdict == Verdict.AC else 0,
            total_tests=1,
            diagnostics=diagnostics,
            sandbox_backend=sandbox_backend
        )
