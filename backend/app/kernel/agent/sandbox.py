from __future__ import annotations

import ast
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from queue import Empty, Queue
from typing import Any


_ALLOWED_IMPORTS = {"decimal", "fractions", "math", "pint", "statistics", "sympy"}
_BLOCKED_NAMES = {
    "__builtins__",
    "__import__",
    "breakpoint",
    "compile",
    "delattr",
    "dir",
    "eval",
    "exec",
    "getattr",
    "globals",
    "help",
    "input",
    "locals",
    "memoryview",
    "open",
    "setattr",
    "vars",
}


@dataclass(frozen=True)
class SandboxResult:
    ok: bool
    value: Any = None
    error: str | None = None


class _SandboxValidator(ast.NodeVisitor):
    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("_"):
            raise ValueError("private and dunder attributes are not allowed")
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._validate_import(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level or not node.module:
            raise ValueError("relative imports are not allowed")
        self._validate_import(node.module)
        for alias in node.names:
            if alias.name == "*" or alias.name.startswith("_"):
                raise ValueError("wildcard and private imports are not allowed")

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in _BLOCKED_NAMES or node.id.startswith("__"):
            raise ValueError(f"name '{node.id}' is not allowed")

    @staticmethod
    def _validate_import(module_name: str) -> None:
        if module_name.split(".", 1)[0] not in _ALLOWED_IMPORTS:
            raise ValueError(f"import '{module_name}' is not allowed")


class PythonSandbox:
    """Execute small deterministic math checks in an isolated restricted process."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 2,
        memory_limit_mb: int = 256,
        max_code_chars: int = 8_000,
        max_output_chars: int = 8_000,
    ):
        if timeout_seconds <= 0 or memory_limit_mb <= 0 or max_code_chars <= 0 or max_output_chars <= 0:
            raise ValueError("sandbox limits must be positive")
        self._timeout_seconds = timeout_seconds
        self._memory_limit_mb = memory_limit_mb
        self._max_code_chars = max_code_chars
        self._max_output_chars = max_output_chars

    def execute(self, code: str) -> SandboxResult:
        if not isinstance(code, str) or not code.strip():
            return SandboxResult(ok=False, error="Python sandbox code is empty")
        if len(code) > self._max_code_chars:
            return SandboxResult(ok=False, error="Python sandbox code is too long")

        try:
            tree = ast.parse(code, mode="exec")
            _SandboxValidator().visit(tree)
        except (SyntaxError, ValueError) as exc:
            return SandboxResult(ok=False, error=f"Python sandbox rejected code: {exc}")

        request = json.dumps(
            {
                "code": code,
                "memory_limit_mb": self._memory_limit_mb,
                "max_output_chars": self._max_output_chars,
                "timeout_seconds": self._timeout_seconds,
            }
        )
        runner_path = Path(__file__).with_name("sandbox_runner.py")
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

        try:
            with tempfile.TemporaryDirectory(prefix="smart-learning-sandbox-", ignore_cleanup_errors=True) as workdir:
                process = subprocess.Popen(
                    [sys.executable, "-I", str(runner_path)],
                    text=True,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=workdir,
                    env=self._sanitized_environment(workdir),
                    creationflags=creation_flags,
                )
                assert process.stdin is not None
                assert process.stdout is not None
                process.stdin.write(request)
                process.stdin.close()

                ready_queue: Queue[str] = Queue(maxsize=1)
                threading.Thread(
                    target=lambda: ready_queue.put(process.stdout.readline()),
                    daemon=True,
                ).start()
                try:
                    ready_line = ready_queue.get(timeout=15)
                except Empty:
                    process.kill()
                    process.wait()
                    self._close_process_streams(process)
                    return SandboxResult(ok=False, error="Python sandbox failed to initialize")
                if ready_line != "READY\n":
                    process.kill()
                    process.wait()
                    detail = (ready_line + process.stderr.read()).strip()[:500]
                    self._close_process_streams(process)
                    return SandboxResult(ok=False, error=f"Python sandbox worker failed: {detail}")

                try:
                    process.wait(timeout=self._timeout_seconds)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    self._close_process_streams(process)
                    return SandboxResult(ok=False, error="Python sandbox timed out")
                raw_output = process.stdout.read().strip()
                raw_error = process.stderr.read().strip()
                self._close_process_streams(process)
        except OSError as exc:
            return SandboxResult(ok=False, error=f"Python sandbox failed to start: {exc}")

        if len(raw_output) > self._max_output_chars:
            return SandboxResult(ok=False, error="Python sandbox output is too large")
        try:
            payload = json.loads(raw_output)
        except json.JSONDecodeError:
            detail = raw_error[:500] or f"worker exited with code {process.returncode}"
            return SandboxResult(ok=False, error=f"Python sandbox worker failed: {detail}")

        if payload.get("ok") is True:
            return SandboxResult(ok=True, value=payload.get("value"))
        return SandboxResult(ok=False, error=str(payload.get("error") or "Python sandbox execution failed"))

    @staticmethod
    def _sanitized_environment(workdir: str) -> dict[str, str]:
        environment = {
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
            "TEMP": workdir,
            "TMP": workdir,
        }
        if os.name == "nt" and os.environ.get("SYSTEMROOT"):
            environment["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
        return environment

    @staticmethod
    def _close_process_streams(process: subprocess.Popen[str]) -> None:
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None and not stream.closed:
                stream.close()
