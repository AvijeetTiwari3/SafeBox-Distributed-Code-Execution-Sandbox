"""
SafeBox: Defense-in-Depth Static Code Security Analyzer
Analyzes submitted source code for adversarial patterns (fork bombs, socket manipulation,
kernel access, shell escapes) prior to compilation/execution.
"""
import ast
import re
from typing import NamedTuple

class SecurityVerdict(NamedTuple):
    is_safe: bool
    violation_reason: str = ""
    rule_triggered: str = ""

# Prohibited patterns in C++ / JS / Shell
FORBIDDEN_PATTERNS: dict[str, list[tuple[re.Pattern, str]]] = {
    "cpp": [
        (re.compile(r"\b(fork|vfork|clone)\b"), "Process spawning / Fork bomb primitive detected"),
        (re.compile(r"\b(socket|connect|bind|listen|accept)\b"), "Network socket access prohibited"),
        (re.compile(r"\b(system|popen|execl|execv|execvp|execle)\b"), "Arbitrary system shell command invocation prohibited"),
        (re.compile(r"\b(kill|ptrace|reboot)\b"), "Kernel process control syscall prohibited"),
        (re.compile(r"#include\s*<sys/socket\.h>"), "Socket headers prohibited"),
        (re.compile(r"#include\s*<unistd\.h>"), "Direct POSIX low-level execution header flagged"),
    ],
    "javascript": [
        (re.compile(r"\b(child_process|cluster)\b"), "Node.js process spawning prohibited"),
        (re.compile(r"\b(net|dgram|http|https)\b"), "Network communication module prohibited"),
        (re.compile(r"\b(process\.kill|process\.abort)\b"), "Process termination manipulation prohibited"),
    ]
}

# Python forbidden modules & calls via AST
FORBIDDEN_PYTHON_MODULES = {
    "socket", "subprocess", "multiprocessing", "threading", "pty",
    "ctypes", "posix", "nt", "_winapi", "win32api", "win32file",
    "http", "urllib", "ftplib", "smtplib"
}

FORBIDDEN_PYTHON_CALLS = {
    "os.system", "os.popen", "os.exec", "os.execv", "os.execvp",
    "os.kill", "os.fork", "os.remove", "os.rmdir", "os.unlink",
    "shutil.rmtree", "eval", "exec", "__import__"
}

class PythonSecurityVisitor(ast.NodeVisitor):
    def __init__(self):
        self.violation: str | None = None
        self.rule: str | None = None

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            base_mod = alias.name.split('.')[0]
            if base_mod in FORBIDDEN_PYTHON_MODULES:
                self.violation = f"Forbidden import: '{alias.name}'"
                self.rule = "IMPORT_DENYLIST"
                return
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            base_mod = node.module.split('.')[0]
            if base_mod in FORBIDDEN_PYTHON_MODULES:
                self.violation = f"Forbidden module import: '{node.module}'"
                self.rule = "IMPORT_DENYLIST"
                return
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts = []
            curr = node.func
            while isinstance(curr, ast.Attribute):
                parts.append(curr.attr)
                curr = curr.value
            if isinstance(curr, ast.Name):
                parts.append(curr.id)
            func_name = ".".join(reversed(parts))

        for forbidden in FORBIDDEN_PYTHON_CALLS:
            if func_name == forbidden or func_name.endswith(f".{forbidden}"):
                self.violation = f"Restricted function invocation: '{func_name}()'"
                self.rule = "RESTRICTED_BUILTIN"
                return

        self.generic_visit(node)

def audit_code(code: str, language: str) -> SecurityVerdict:
    """
    Performs static security analysis against the submitted payload.
    """
    language = language.lower()

    if language == "python":
        try:
            tree = ast.parse(code)
            visitor = PythonSecurityVisitor()
            visitor.visit(tree)
            if visitor.violation:
                return SecurityVerdict(False, visitor.violation, visitor.rule or "STATIC_RULE")
        except SyntaxError:
            # Let compilation/runner engine catch syntax errors naturally
            pass

    patterns = FORBIDDEN_PATTERNS.get(language, [])
    for regex, reason in patterns:
        if regex.search(code):
            return SecurityVerdict(False, reason, "PATTERN_DENYLIST")

    # Common fork bomb heuristic
    if re.search(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;", code):
        return SecurityVerdict(False, "Classic bash fork-bomb signature detected", "FORK_BOMB")

    return SecurityVerdict(True)
