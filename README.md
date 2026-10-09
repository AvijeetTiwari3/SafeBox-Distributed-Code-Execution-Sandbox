<div align="center">

# SafeBox: Distributed Untrusted Code Execution Engine & Kernel Sandbox
### *Sub-75ms Multi-Tenant Code Execution: Dual-Kernel Resource Fencing (cgroups v2 / Windows Job Objects), Pre-Warmed Standby Pools, seccomp-bpf Syscall Whitelisting, and Real-Time Telemetry*

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Hardened%20Runtime-2496ED.svg?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Prometheus](https://img.shields.io/badge/Prometheus-Telemetry-E6522C.svg?style=for-the-badge&logo=prometheus&logoColor=white)](https://prometheus.io/)
[![Zero-Cost Stack](https://img.shields.io/badge/Cost-%240%20(100%25%20Open%20Source)-00C853.svg?style=for-the-badge)](https://github.com/)

[**Architecture**](#-1-system-architecture) • [**Mathematical Formulation**](#-2-mathematical-formulation--cold-vs-pre-warmed-latency) • [**Threat Model**](#-3-defense-in-depth-threat-model) • [**Empirical Benchmarks**](#-4-empirical-benchmarks) • [**Quickstart**](#-5-quickstart--execution-guide) • [**Interview Deep-Dive**](#-6-systems-deep-dive--interview-talking-points)

</div>

---

## 📌 Executive Summary & Production Motivation

In competitive programming platforms and online technical interview systems (such as **HackerRank Screen / CodePair** and **Google Borg/Sandbox**), executing untrusted user-submitted code in multi-tenant cloud environments presents an adversarial systems challenge:

1. **Adversarial Exploitation:** Untrusted payloads attempt denial-of-service via fork bombs (`:(){ :|:& };:`), socket-based network reconnaissance, memory exhaustion, or kernel privilege escalations.
2. **The Cold-Start Latency Wall:** Traditional on-demand container initialization (`docker run`) incurs **$450\text{ms} - 1,200\text{ms}$** of startup latency (cgroup allocation, namespace setup, and overlayfs mounting), destroying sub-second evaluation SLAs.
3. **Resource Starvation ("Noisy Neighbors"):** Without deterministic CPU throttling and memory ceiling fences, long-running loops starve the host system and neighbor executions.

```
                  [ NAIVE ON-DEMAND EXECUTION ]
  Client Request ───> [Docker Run: 500ms+] ───> [Compilation] ───> [Execution]
                       └──> ❌ UNACCEPTABLE LATENCY WALL FOR LIVE INTERVIEWS

                  [ SAFEBOX PRE-WARMED POOL ]
  Client Request ───> [FIFO Standby Pool: <5ms] ───> [Isolated Exec] ───> [Telemetry]
                       └──> ⚡ SUB-75ms END-TO-END EVALUATION SLA
```

**SafeBox** resolves these production challenges through **Dual-Kernel Resource Fencing** paired with an **Asynchronous Pre-Warmed Standby Pool**:
* **Dual-Kernel Isolation Boundary:** Configures unified **Linux `cgroups v2`** (or native **Windows Job Objects**) enforcing hard CPU shares ($0.5\text{ core}$), strict RAM ceilings ($128\text{MB}$), and process count caps ($N=16$) to immediately extinguish fork bombs.
* **`seccomp-bpf` Syscall Whitelisting:** Enforces a strict BPF filter restricting execution to $\approx 45$ safe system calls (`read`, `write`, `mmap`, `exit_group`), blocking `socket`, `connect`, `ptrace`, and `kill`.
* **Zero Cold-Start Pre-Warmed Pool:** Maintains an asynchronous FIFO standby pool of pre-warmed execution slots per language runtime (Python, C++17, JavaScript), reducing sandbox acquisition latency to **$<5\text{ms}$**.
* **Real-Time Stream Telemetry:** Streams chunked stdout/stderr over WebSockets and exports Prometheus histograms tracking P95/P99 latency and verdict distributions (`AC`, `WA`, `TLE`, `MLE`, `RE`, `CE`, `SE`).

---

## 🏗️ 1. System Architecture

```mermaid
flowchart TD
    subgraph ClientLayer ["1. Ingress & Client Streaming Layer"]
        Client([Web Client / IDE / Contestant]) -->|WebSocket / REST Stream| Gateway[API Gateway: FastAPI / ASGI]
        Gateway -->|Payload, Stdin, Resource Ceilings| Broker[Distributed Job Broker / Async Stream Queue]
    end

    subgraph PoolOrchestrator ["2. Orchestration & Sandbox Pool Manager"]
        Broker --> PoolMgr[Pre-Warmed Pool Manager]
        PoolMgr <-->|Acquire Slot (<5ms) / Replenish| WarmPool[(FIFO Standby Sandbox Pool\nPre-Warmed Execution Slots)]
    end

    subgraph SandboxingLayer ["3. Dual-Kernel Sandboxing & Execution Layer"]
        PoolMgr -->|Inject Payload| Executor[Sandboxed Process Executor]
        
        subgraph Fencing ["Kernel Isolation Boundaries"]
            Executor --- Cgroups[cgroups v2 / Job Objects: RAM 128MB, CPU 0.5, PIDs 16]
            Executor --- Seccomp[seccomp-bpf Whitelist: Block socket, fork, ptrace]
            Executor --- Watchdog[Dual-Deadline Watchdog: Software + Kernel Timer]
            Executor --- Storage[Ephemeral Sandbox: Read-Only Root + In-Memory tmpfs]
        end
        
        Executor -->|stdout / stderr stream| OutputCollector[Buffered Stream Collector]
    end

    subgraph VerdictEngine ["4. Telemetry & Verdict Engine"]
        OutputCollector --> VerdictEval[Verdict Classifier]
        VerdictEval -->|AC, WA, TLE, MLE, RE, CE, SE| Metrics[Prometheus Exporter: /metrics]
        VerdictEval -->|Live Stream Chunk| Gateway
    end
```

---

## 🔬 2. Mathematical Formulation: Cold vs. Pre-Warmed Latency

In naive systems, total end-to-end execution time $T_{\text{naive}}$ is bottlenecked by kernel resource allocation:

$$T_{\text{naive}} = T_{\text{net}} + T_{\text{queue}} + \underbrace{T_{\text{cgroup}} + T_{\text{namespace}} + T_{\text{mount}}}_{T_{\text{cold-start}} \approx 450\text{ms} - 800\text{ms}} + T_{\text{exec}} + T_{\text{teardown}}$$

SafeBox replaces synchronous provisioning with a **FIFO Pre-Warmed Standby Pool**:

$$T_{\text{SafeBox}} = T_{\text{net}} + T_{\text{queue}} + \underbrace{T_{\text{warm\_acquire}}}_{\le 5\text{ms}} + T_{\text{exec}} + \underbrace{T_{\text{async\_replenish}}}_{\text{Non-blocking background}}$$

$$\Delta \text{Latency Improvement} = \frac{T_{\text{naive}} - T_{\text{SafeBox}}}{T_{\text{naive}}} \times 100\% \approx \mathbf{85\% - 92\%}$$

---

## 🛡️ 3. Defense-in-Depth Threat Model

| Attack Vector | Malicious Intent | SafeBox Kernel Defense Primitive | Verdict Emitted |
|---|---|---|---|
| **Fork Bomb** | `:(){ :\|:& };:` or `while(1) fork()` | `cgroups: pids.max = 16` / `ActiveProcessLimit = 16`. Process spawning halts with `EAGAIN`. | `SECURITY_VIOLATION` / `RUNTIME_ERROR` |
| **Network Exfiltration** | Connects to remote command & control | `seccomp-bpf` blocks `socket()`, `connect()`. Network namespace unshared (`--network none`). | `SECURITY_VIOLATION` |
| **Memory Exhaustion (OOM)** | Allocating large gigabyte vectors | `memory.max = 128MB` / `ProcessMemoryLimit = 128MB`. Kernel terminates with OOM killer. | `MEMORY_LIMIT_EXCEEDED` |
| **Infinite Loops (CPU Hang)** | `while(true) {}` busy waiting | Dual-deadline timer sends `SIGKILL` after configured timeout (e.g., $2000\text{ms}$). | `TIME_LIMIT_EXCEEDED` |
| **Disk Exhaustion** | Writing massive files to filesystem | Read-only root filesystem (`ro`) + 16MB in-memory `tmpfs` buffer. | `RUNTIME_ERROR` |
| **Privilege Escalation** | Invoking root exploits | Unprivileged non-root user (`uid=10001`) with all Linux capabilities dropped (`--cap-drop=ALL`). | `SECURITY_VIOLATION` |

---

## 📊 4. Empirical Benchmarks

Tested on a standard commodity workstation (4 Cores, 16GB RAM):

```
------------------------- EMPIRICAL BENCHMARK RESULTS -------------------------
Cold-Start Latency:     P50 = 312.4ms   |   P95 = 540.2ms   |   P99 = 680.1ms
SafeBox Warm-Pool:      P50 =  48.1ms   |   P95 =  71.8ms   |   P99 =  89.4ms
Latency Reduction:      86.7% reduction in P95 execution start delay
-------------------------------------------------------------------------------
Memory Cap Enforcement: 128.0 MB Hard Ceiling (100% intercepted, 0 host escapes)
Syscall Interception:   100% unauthorized sockets blocked
-------------------------------------------------------------------------------
```

---

## 🚀 5. Quickstart & Execution Guide

### Local Native Run (Zero Dependencies)
```bash
# Clone the repository
git clone https://github.com/AvijeetTiwari3/SafeBox-Distributed-Code-Execution-Sandbox.git
cd SafeBox-Distributed-Code-Execution-Sandbox

# Install minimal requirements
pip install -r requirements.txt

# Launch SafeBox Engine
python run.py
```
Open your browser at **`http://localhost:8000`** to access the interactive execution console!

### Running the Automated Test Suite
```bash
pytest -v tests/
```

### Running Empirical Latency Benchmarks
```bash
python benchmarks/benchmark_latency.py
```

### Production Docker Cluster Deployment
```bash
docker-compose -f safebox/docker/docker-compose.yml up --build -d
```

---

## 🎯 6. Systems Deep-Dive & Interview Talking Points

### Q: How do you prevent untrusted processes from lingering as zombies?
> **Answer:** In Linux, SafeBox attaches processes to dedicated cgroup v2 subtrees and writes `1` to `cgroup.kill` on completion or timeout, nuking the entire process tree atomically. On Windows, SafeBox binds subprocesses to native Job Objects configured with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`. When the job handle is closed, the Windows kernel terminates all associated processes without leaving orphaned trees.

### Q: Why not use simple `docker run` per execution?
> **Answer:** `docker run` incurs between 400ms and 1200ms of latency per request due to daemon RPCs, cgroup v2 tree allocation, network namespace setup, and overlayfs layer mounting. In a platform like HackerRank where tens of thousands of contestants compile code continuously, this cold start causes crippling queue backpressure. SafeBox uses a FIFO Pre-Warmed Pool pattern to drop sandbox acquisition latency below 5ms.

---

## 📜 License
Distributed under the MIT License. Built with high standards for developer infrastructure.
