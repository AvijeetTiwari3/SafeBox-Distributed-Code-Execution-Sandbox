import requests

def test_live():
    print("--- 1. Testing C++ Compilation & Execution ---")
    r = requests.post("http://localhost:8000/api/v1/execute", json={
        "code": "#include <iostream>\nint main() { std::cout << 999 * 3 << std::endl; return 0; }",
        "language": "cpp",
        "expected_output": "2997"
    })
    data = r.json()
    print("C++ Verdict:", data["verdict"], "| Output:", data["stdout"].strip(), "| Compile Time:", data["compilation_time_ms"], "ms")
    assert data["verdict"] == "ACCEPTED"

    print("\n--- 2. Testing JavaScript (Node.js) ---")
    r2 = requests.post("http://localhost:8000/api/v1/execute", json={
        "code": "console.log('SafeBox JS Engine Status: Operational');",
        "language": "javascript"
    })
    data2 = r2.json()
    print("JS Verdict:", data2["verdict"], "| Output:", data2["stdout"].strip())
    assert data2["verdict"] == "ACCEPTED"

    print("\n--- 3. Testing Security Sandbox Rejection ---")
    r3 = requests.post("http://localhost:8000/api/v1/execute", json={
        "code": "import socket\ns = socket.socket()",
        "language": "python"
    })
    data3 = r3.json()
    print("Security Verdict:", data3["verdict"], "| Diagnostics:", data3["diagnostics"])
    assert data3["verdict"] == "SECURITY_VIOLATION"

    print("\n--- 4. Testing Time Limit Exceeded (TLE) Watchdog ---")
    r4 = requests.post("http://localhost:8000/api/v1/execute", json={
        "code": "while True: pass",
        "language": "python"
    })
    data4 = r4.json()
    print("TLE Verdict:", data4["verdict"], "| Duration:", data4["execution_time_ms"], "ms")
    assert data4["verdict"] == "TIME_LIMIT_EXCEEDED"

    print("\n>> ALL LIVE ENDPOINTS & RUNTIMES PASSED VALIDATION! <<")

if __name__ == "__main__":
    test_live()
