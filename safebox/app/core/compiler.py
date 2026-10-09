"""
SafeBox: Multi-Language Compilation Engine
Manages ephemeral build pipelines, compiler flags, and diagnostics for compiled languages (C++, etc.).
"""
import subprocess
import time
from pathlib import Path
from .config import SUPPORTED_LANGUAGES, LanguageConfig

class CompilationResult:
    def __init__(self, success: bool, binary_path: Path | None, error_msg: str = "", duration_ms: float = 0.0):
        self.success = success
        self.binary_path = binary_path
        self.error_msg = error_msg
        self.duration_ms = duration_ms

def compile_source(source_path: Path, language: str) -> CompilationResult:
    """
    Compiles source file into a binary executable inside the designated build workspace.
    """
    lang_cfg: LanguageConfig | None = SUPPORTED_LANGUAGES.get(language)
    if not lang_cfg or not lang_cfg.compiled:
        return CompilationResult(True, source_path, duration_ms=0.0)

    work_dir = source_path.parent
    binary_name = source_path.stem + (".exe" if subprocess.os.name == "nt" else "")
    binary_path = work_dir / binary_name

    # Build command substitution
    cmd = []
    for token in lang_cfg.compile_cmd:
        formatted = token.replace("{file}", str(source_path)).replace("{output}", str(binary_path))
        cmd.append(formatted)

    start_t = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=work_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10.0  # Max 10s compile time
        )
        duration_ms = (time.perf_counter() - start_t) * 1000.0

        if proc.returncode != 0:
            return CompilationResult(
                success=False,
                binary_path=None,
                error_msg=proc.stderr or proc.stdout or "Compilation failed",
                duration_ms=round(duration_ms, 2)
            )

        return CompilationResult(
            success=True,
            binary_path=binary_path,
            duration_ms=round(duration_ms, 2)
        )
    except subprocess.TimeoutExpired:
        return CompilationResult(
            success=False,
            binary_path=None,
            error_msg="Compilation timed out (limit: 10s)",
            duration_ms=10000.0
        )
    except Exception as e:
        return CompilationResult(
            success=False,
            binary_path=None,
            error_msg=f"Compiler invocation error: {str(e)}",
            duration_ms=0.0
        )
