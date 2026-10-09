"""
SafeBox: Configuration & Global Runtime Parameters
Defines strict resource limits, kernel thresholds, and language execution profiles.
"""
from pathlib import Path
from pydantic import BaseModel, Field
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SANDBOX_TEMP_DIR = BASE_DIR / ".safebox_tmp"
SANDBOX_TEMP_DIR.mkdir(parents=True, exist_ok=True)

class ResourceLimits(BaseModel):
    # Execution ceilings
    time_limit_ms: int = Field(default=2000, description="Max wall-clock/CPU execution time in ms")
    memory_limit_mb: int = Field(default=128, description="Max physical memory allocated in MB")
    max_output_bytes: int = Field(default=65536, description="Max stdout/stderr output size (64KB buffer)")
    max_processes: int = Field(default=16, description="Max concurrent child processes / threads (fork bomb guard)")
    cpu_cores: float = Field(default=1.0, description="Fractional CPU quota")

class LanguageConfig(BaseModel):
    id: str
    name: str
    extension: str
    compiled: bool
    compile_cmd: list[str] = []
    run_cmd: list[str] = []
    default_template: str = ""

# Language profiles
SUPPORTED_LANGUAGES: dict[str, LanguageConfig] = {
    "python": LanguageConfig(
        id="python",
        name="Python 3",
        extension=".py",
        compiled=False,
        run_cmd=["python", "-u", "{file}"],
        default_template="""import sys

def solve():
    lines = sys.stdin.read().split()
    if not lines:
        print("Hello, SafeBox Sandbox!")
        return
    print(f"Processed {len(lines)} tokens: {lines}")

if __name__ == '__main__':
    solve()
"""
    ),
    "cpp": LanguageConfig(
        id="cpp",
        name="C++ (GCC/MinGW C++17)",
        extension=".cpp",
        compiled=True,
        compile_cmd=["g++", "-O2", "-std=c++17", "-Wall", "{file}", "-o", "{output}"],
        run_cmd=["{output}"],
        default_template="""#include <iostream>
#include <vector>
#include <numeric>

int main() {
    std::ios_base::sync_with_stdio(false);
    std::cin.tie(NULL);
    std::cout << "Hello from SafeBox C++ Sandbox\\n";
    return 0;
}
"""
    ),
    "javascript": LanguageConfig(
        id="javascript",
        name="JavaScript (Node.js)",
        extension=".js",
        compiled=False,
        run_cmd=["node", "{file}"],
        default_template="""const fs = require('fs');

function main() {
    const input = fs.readFileSync(0, 'utf-8').trim();
    console.log("SafeBox JS Execution Complete");
    if (input) console.log("Input received:", input);
}

main();
"""
    )
}

class Settings:
    PROJECT_NAME: str = "SafeBox"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"
    DEFAULT_LIMITS: ResourceLimits = ResourceLimits()
    WARM_POOL_SIZE_PER_LANG: int = int(os.getenv("SAFEBOX_POOL_SIZE", "3"))
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    ENABLE_STATIC_ANALYSIS: bool = True
    MAX_PAYLOAD_CODE_BYTES: int = 128 * 1024  # 128 KB max source file

settings = Settings()
