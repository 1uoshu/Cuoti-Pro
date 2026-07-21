from __future__ import annotations

import importlib
import json
import math
import sys
from typing import Any

from RestrictedPython import compile_restricted
from RestrictedPython.Eval import default_guarded_getitem, default_guarded_getiter
from RestrictedPython.Guards import (
    full_write_guard,
    guarded_iter_unpack_sequence,
    guarded_unpack_sequence,
    safe_builtins,
    safer_getattr,
)
from RestrictedPython.PrintCollector import PrintCollector


ALLOWED_IMPORTS = {"decimal", "fractions", "math", "pint", "statistics", "sympy"}


def _restricted_import(
    name: str,
    globals: dict[str, Any] | None = None,
    locals: dict[str, Any] | None = None,
    fromlist: tuple[str, ...] | None = (),
    level: int = 0,
) -> Any:
    del globals, locals
    if level or name.split(".", 1)[0] not in ALLOWED_IMPORTS:
        raise ImportError(f"import '{name}' is not allowed")
    resolved_fromlist = fromlist or ()
    if any(item == "*" or item.startswith("_") for item in resolved_fromlist):
        raise ImportError("wildcard and private imports are not allowed")
    return __import__(name, fromlist=resolved_fromlist)


def _apply_resource_limits(memory_limit_mb: int, timeout_seconds: float) -> None:
    try:
        import resource
    except ImportError:
        return

    memory_bytes = memory_limit_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    consumed_cpu = resource.getrusage(resource.RUSAGE_SELF).ru_utime
    cpu_seconds = math.ceil(consumed_cpu + max(1, timeout_seconds))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))


def _execute(request: dict[str, Any]) -> dict[str, Any]:
    _apply_resource_limits(int(request["memory_limit_mb"]), float(request["timeout_seconds"]))
    builtins = dict(safe_builtins)
    builtins["__import__"] = _restricted_import
    namespace: dict[str, Any] = {
        "__builtins__": builtins,
        "_getattr_": safer_getattr,
        "_getitem_": default_guarded_getitem,
        "_getiter_": default_guarded_getiter,
        "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
        "_print_": PrintCollector,
        "_unpack_sequence_": guarded_unpack_sequence,
        "_write_": full_write_guard,
    }
    byte_code = compile_restricted(request["code"], filename="<python_verify>", mode="exec")
    exec(byte_code, namespace, namespace)
    if "result" not in namespace:
        raise ValueError("code must assign a JSON-serializable value to result")
    json.dumps(namespace["result"], ensure_ascii=False, allow_nan=False)
    return {"ok": True, "value": namespace["result"]}


def main() -> None:
    request: dict[str, Any] = {}
    try:
        request = json.loads(sys.stdin.read())
        for module_name in sorted(ALLOWED_IMPORTS):
            importlib.import_module(module_name)
        sys.stdout.write("READY\n")
        sys.stdout.flush()
        response = _execute(request)
    except BaseException as exc:
        response = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    output = json.dumps(response, ensure_ascii=False, allow_nan=False)
    max_output_chars = int(request.get("max_output_chars", 8_000)) if isinstance(request, dict) else 8_000
    if len(output) > max_output_chars:
        output = json.dumps({"ok": False, "error": "Python sandbox output is too large"})
    sys.stdout.write(output)


if __name__ == "__main__":
    main()
