// SafeBox Frontend Client Controller

const PRESETS = {
    python: {
        ac: `import sys

def solve():
    print("Executing quicksort benchmark inside SafeBox sandbox...")
    arr = [64, 34, 25, 12, 22, 11, 90]
    arr.sort()
    print("Sorted Output:", arr)
    print("Sandbox Isolation: Verified Safe.")

if __name__ == "__main__":
    solve()`,
        tle: `# Time Limit Exceeded (TLE) Exploit Simulation
# Attempting to exhaust CPU via infinite computation
import time

print("Commencing infinite compute loop...")
counter = 0
while True:
    counter += 1`,
        mle: `# Memory Limit Exceeded (MLE) Exploit Simulation
# Attempting to exhaust memory beyond 128MB ceiling
print("Attempting to allocate 500MB buffer in memory...")
# Allocate large array exceeding container memory limit
bomb = [0] * (60 * 1024 * 1024)
print("Allocated successfully?", len(bomb))`,
        fork: `# Fork Bomb / Process Flood Exploit
import os

print("Attempting to spawn multiple processes...")
for i in range(100):
    try:
        os.fork()
    except Exception as e:
        print(f"Process spawn failed at iteration {i}: {e}")
        break`,
        socket: `# Socket Exfiltration Exploit
import socket

print("Attempting to open raw TCP socket to external network...")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("8.8.8.8", 53))`
    },
    cpp: {
        ac: `#include <iostream>
#include <vector>
#include <algorithm>

int main() {
    std::ios_base::sync_with_stdio(false);
    std::cin.tie(NULL);

    std::vector<int> nums = {99, 12, 45, 1, 88, 34};
    std::sort(nums.begin(), nums.end());

    std::cout << "SafeBox C++ Benchmark: Sorted Array:\\n";
    for (int n : nums) std::cout << n << " ";
    std::cout << "\\nZero-Cold-Start verified.\\n";
    return 0;
}`,
        tle: `#include <iostream>

int main() {
    std::cout << "Attempting C++ infinite busy loop...\\n";
    volatile long long counter = 0;
    while (true) {
        counter++;
    }
    return 0;
}`,
        mle: `#include <iostream>
#include <vector>

int main() {
    std::cout << "Attempting 300MB heap allocation...\\n";
    std::vector<char> big_buffer(300 * 1024 * 1024, 'X');
    std::cout << "Buffer allocated! Size: " << big_buffer.size() << "\\n";
    return 0;
}`,
        fork: `#include <iostream>
#include <unistd.h>

int main() {
    std::cout << "Attempting POSIX fork bomb...\\n";
    while (1) {
        fork();
    }
    return 0;
}`,
        socket: `#include <iostream>
#include <sys/socket.h>

int main() {
    std::cout << "Attempting raw network socket creation...\\n";
    int s = socket(AF_INET, SOCK_STREAM, 0);
    return 0;
}`
    },
    javascript: {
        ac: `console.log("SafeBox Node.js Engine Initialized");
const data = [10, 5, 2, 8, 1, 9];
data.sort((a, b) => a - b);
console.log("Result:", data);`,
        tle: `console.log("Starting Node.js event-loop freeze...");
while (true) {}`,
        mle: `console.log("Allocating 400MB in Node.js heap...");
const buffers = [];
for (let i = 0; i < 50; i++) {
    buffers.push(Buffer.alloc(10 * 1024 * 1024));
}`,
        fork: `const cp = require('child_process');
console.log("Attempting child process spawn...");
cp.fork();`,
        socket: `const net = require('net');
console.log("Attempting socket creation...");
const client = net.createConnection({ port: 80, host: 'google.com' });`
    }
};

const langSelect = document.getElementById('lang-select');
const codeEditor = document.getElementById('code-editor');
const editorFilename = document.getElementById('editor-filename');
const terminalStdout = document.getElementById('terminal-stdout');
const verdictText = document.getElementById('verdict-text');
const verdictBadge = document.getElementById('verdict-badge');
const verdictBanner = document.getElementById('verdict-banner');
const metricTime = document.getElementById('metric-time');
const metricMemory = document.getElementById('metric-memory');
const metricExitCode = document.getElementById('metric-exitcode');
const diagnosticsText = document.getElementById('diagnostics-text');
const streamIndicator = document.getElementById('stream-indicator');
const runSpinner = document.getElementById('run-spinner');
const runBtn = document.getElementById('run-btn');
const poolSlotsCount = document.getElementById('pool-slots-count');
const sandboxTypeElem = document.getElementById('sandbox-type');

function updateEditorLang() {
    const lang = langSelect.value;
    const extensions = { python: "solution.py", cpp: "solution.cpp", javascript: "solution.js" };
    editorFilename.innerText = extensions[lang] || "solution.txt";
    loadPreset('ac');
}

langSelect.addEventListener('change', updateEditorLang);

function loadPreset(key) {
    const lang = langSelect.value;
    const code = PRESETS[lang]?.[key] || PRESETS.python.ac;
    codeEditor.value = code;
}

async function fetchPoolStats() {
    try {
        const res = await fetch('/api/v1/pool/stats');
        const data = await res.json();
        const activeCap = Object.values(data.pool_capacities || {}).reduce((a, b) => a + b, 0);
        poolSlotsCount.innerText = `${activeCap} slots active`;
    } catch (e) {
        poolSlotsCount.innerText = "Active";
    }
}

async function executePayload() {
    const lang = langSelect.value;
    const code = codeEditor.value;
    const stdin = document.getElementById('stdin-input').value;
    const expected = document.getElementById('expected-output').value || null;

    runSpinner.classList.remove('hidden');
    runBtn.disabled = true;
    streamIndicator.innerText = "Executing in sandbox...";
    terminalStdout.innerText = ">> Provisioning isolated workspace...\n>> Binding kernel limits (cgroups/Job Object)...";

    const startClientT = performance.now();

    try {
        const response = await fetch('/api/v1/execute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                code: code,
                language: lang,
                stdin_data: stdin,
                expected_output: expected
            })
        });

        const result = await response.json();
        const clientLatency = Math.round(performance.now() - startClientT);

        renderResult(result, clientLatency);
    } catch (err) {
        terminalStdout.innerText = `Network/Server Error: ${err.message}`;
        setVerdict("ERROR", "bg-rose-500/10 border-rose-500/30 text-rose-400");
    } finally {
        runSpinner.classList.add('hidden');
        runBtn.disabled = false;
        streamIndicator.innerText = "Idle";
        fetchPoolStats();
    }
}

function renderResult(result, clientLatency) {
    // Terminal content
    let out = result.stdout || "";
    if (result.stderr) {
        out += (out ? "\n\n" : "") + "--- STDERR / COMPILER DIAGNOSTICS ---\n" + result.stderr;
    }
    if (!out) {
        out = "[No output generated]";
    }
    terminalStdout.innerText = out;

    // Metrics
    metricTime.innerText = `${result.execution_time_ms} ms`;
    metricMemory.innerText = `${result.peak_memory_mb} MB`;
    metricExitCode.innerText = result.exit_code !== undefined ? result.exit_code : "-";
    diagnosticsText.innerText = result.diagnostics || "Execution verified by kernel guard.";
    sandboxTypeElem.innerText = result.sandbox_backend || "OS Kernel";

    // Verdict Badge
    const v = result.verdict;
    if (v === "ACCEPTED") {
        setVerdict("ACCEPTED", "bg-emerald-500/10 border-emerald-500/30 text-emerald-400");
    } else if (v === "TIME_LIMIT_EXCEEDED") {
        setVerdict("TIME LIMIT EXCEEDED", "bg-amber-500/10 border-amber-500/30 text-amber-400");
    } else if (v === "MEMORY_LIMIT_EXCEEDED") {
        setVerdict("MEMORY LIMIT EXCEEDED", "bg-purple-500/10 border-purple-500/30 text-purple-400");
    } else if (v === "SECURITY_VIOLATION") {
        setVerdict("SECURITY REJECTION", "bg-red-500/10 border-red-500/30 text-red-400");
    } else if (v === "COMPILATION_ERROR") {
        setVerdict("COMPILATION ERROR", "bg-orange-500/10 border-orange-500/30 text-orange-400");
    } else if (v === "WRONG_ANSWER") {
        setVerdict("WRONG ANSWER", "bg-rose-500/10 border-rose-500/30 text-rose-400");
    } else {
        setVerdict(v, "bg-slate-800 border-slate-700 text-slate-300");
    }
}

function setVerdict(label, colorClasses) {
    verdictText.innerText = label;
    verdictBadge.innerText = label;
    verdictBanner.className = `p-4 rounded-lg border transition-all ${colorClasses}`;
    verdictBadge.className = `px-3 py-1 rounded-md text-xs font-semibold ${colorClasses}`;
}

function clearConsole() {
    terminalStdout.innerText = "Console cleared.";
    metricTime.innerText = "0.0 ms";
    metricMemory.innerText = "0.0 MB";
    metricExitCode.innerText = "-";
    setVerdict("IDLE", "bg-slate-900 border-slate-800 text-slate-300");
    diagnosticsText.innerText = "Ready for execution.";
}

// Initial setup
updateEditorLang();
fetchPoolStats();
setInterval(fetchPoolStats, 5000);
