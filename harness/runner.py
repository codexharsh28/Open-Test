"""Timeout-bounded pytest subprocess execution."""

from __future__ import annotations

import math
import os
import subprocess
import sys
from pathlib import Path


def run_test(test_file: str, timeout: int = 10) -> dict[str, object]:
    """Run one pytest file and capture its output.

    The subprocess is always terminated after ``timeout`` seconds. The return
    shape stays stable for callers, including when pytest cannot be started or
    the timeout expires.
    """
    result: dict[str, object] = {
        "passed": False,
        "stdout": "",
        "stderr": "",
        "returncode": -1,
    }
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout)
        or timeout <= 0
    ):
        result["stderr"] = "timeout must be a positive number of seconds"
        return result
    if not isinstance(test_file, str) or not test_file.strip():
        result["stderr"] = "test_file must be a non-empty path"
        return result

    test_path = Path(test_file).expanduser()
    if not test_path.is_absolute():
        test_path = Path.cwd() / test_path
    if not test_path.is_file():
        result["stderr"] = f"pytest test file does not exist: {test_path}"
        return result

    command = [sys.executable, "-m", "pytest", str(test_path), "--maxfail=1", "-v"]
    env = os.environ.copy()
    env.pop("PYTEST_ADDOPTS", None)
    try:
        completed = subprocess.run(
            command,
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            timeout=float(timeout),
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = _decode_output(exc.stdout)
        stderr = _decode_output(exc.stderr)
        timeout_message = f"pytest timed out after {timeout} seconds"
        result.update(
            stdout=stdout,
            stderr=f"{stderr}\n{timeout_message}".strip(),
            returncode=124,
        )
    except OSError as exc:
        result["stderr"] = f"could not start pytest: {exc}"
    else:
        result.update(
            passed=completed.returncode == 0,
            stdout=completed.stdout,
            stderr=completed.stderr,
            returncode=completed.returncode,
        )
    return result


def _decode_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
