"""
SafeBox Test Suite: Core Execution Engine
Validates normal execution, multi-language support (Python, C++, JS), and verdict classifications.
"""
import pytest
import asyncio
from safebox.app.core.executor import SandboxedExecutor
from safebox.app.core.verdict import Verdict

@pytest.mark.asyncio
async def test_python_accepted():
    executor = SandboxedExecutor()
    code = """
import sys
x = sys.stdin.read().strip()
print(f"Echo: {x}")
"""
    result = await executor.execute(
        code=code,
        language="python",
        stdin_data="42",
        expected_output="Echo: 42"
    )
    assert result.verdict == Verdict.AC
    assert result.exit_code == 0
    assert "Echo: 42" in result.stdout

@pytest.mark.asyncio
async def test_python_wrong_answer():
    executor = SandboxedExecutor()
    code = "print('Hello World')"
    result = await executor.execute(
        code=code,
        language="python",
        expected_output="Goodbye World"
    )
    assert result.verdict == Verdict.WA
    assert "Output mismatch" in result.diagnostics

@pytest.mark.asyncio
async def test_python_runtime_error():
    executor = SandboxedExecutor()
    code = "x = 1 / 0"
    result = await executor.execute(code=code, language="python")
    assert result.verdict == Verdict.RE
    assert result.exit_code != 0
    assert "ZeroDivisionError" in result.stderr

@pytest.mark.asyncio
async def test_cpp_accepted():
    executor = SandboxedExecutor()
    code = """
#include <iostream>
int main() {
    int a, b;
    if (std::cin >> a >> b) {
        std::cout << (a + b) << "\\n";
    }
    return 0;
}
"""
    result = await executor.execute(
        code=code,
        language="cpp",
        stdin_data="15 27",
        expected_output="42"
    )
    assert result.verdict == Verdict.AC
    assert "42" in result.stdout.strip()
    assert result.compilation_time_ms > 0

@pytest.mark.asyncio
async def test_cpp_compilation_error():
    executor = SandboxedExecutor()
    code = """
#include <iostream>
int main() {
    this_is_invalid_syntax_error();
    return 0;
}
"""
    result = await executor.execute(code=code, language="cpp")
    assert result.verdict == Verdict.CE
    assert "Code compilation failed" in result.diagnostics

@pytest.mark.asyncio
async def test_javascript_accepted():
    executor = SandboxedExecutor()
    code = "console.log('SafeBox JS OK');"
    result = await executor.execute(
        code=code,
        language="javascript",
        expected_output="SafeBox JS OK"
    )
    assert result.verdict == Verdict.AC
    assert "SafeBox JS OK" in result.stdout
