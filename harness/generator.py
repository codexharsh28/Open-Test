"""Generate pytest tests with local Ollama and repair failures iteratively."""

from __future__ import annotations

import argparse
import ipaddress
import os
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

try:
    from ollama import Client
except ImportError:  # Keep the UI importable when optional runtime packages are absent.
    Client = None  # type: ignore[assignment,misc]

from .ast_inspector import inspect_python
from .runner import run_test


ProgressCallback = Callable[[dict[str, Any]], None]


class TestForgeEngine:
    """Use a local Ollama model to generate and self-heal pytest tests."""

    def __init__(self, model: str = "qwen2.5-coder:3b") -> None:
        self.model = model
        # Bind only to loopback: this harness does not use external model APIs.
        self.host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
        self.configuration_error = self._validate_local_host(self.host)
        self.client = Client(host=self.host, trust_env=False) if Client and not self.configuration_error else None

    def generate_and_heal(
        self,
        source_code: str,
        test_file: str = "test_target.py",
        max_retries: int = 3,
        on_event: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Generate tests, then repair them using pytest output until passing.

        ``max_retries`` counts repairs after the initial generation. Thus the
        default allows up to four executions. ``on_event`` is optional and is
        used by the Streamlit UI to display each state transition.
        """
        if not isinstance(source_code, str) or not source_code.strip():
            return self._failure("source_code must be a non-empty string", test_file)
        if isinstance(max_retries, bool) or not isinstance(max_retries, int) or max_retries < 0:
            return self._failure("max_retries must be a non-negative integer", test_file)
        if not isinstance(test_file, str) or not test_file.strip():
            return self._failure("test_file must be a non-empty path", test_file)
        if self.client is None:
            message = self.configuration_error or "The ollama package is not installed. Install requirements.txt first."
            return self._failure(message, test_file)

        destination = Path(test_file).expanduser()
        if not destination.is_absolute():
            destination = Path.cwd() / destination

        history: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "You generate correct, concise pytest tests for the supplied Python module. "
                    "Return only executable Python test code, with no markdown fences. Import the "
                    "module as target_code. Test its documented behavior; do not modify production code."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Write pure pytest tests for target_code.py using this complete source:\n\n"
                    f"```python\n{source_code}\n```"
                ),
            },
        ]
        events: list[str] = []
        last_result: dict[str, Any] = {"passed": False, "stdout": "", "stderr": "", "returncode": -1}

        for attempt in range(max_retries + 1):
            iteration = attempt + 1
            self._emit(on_event, events, f"Iteration {iteration}: requesting test code from local {self.model} model.")
            try:
                response = self.client.chat(model=self.model, messages=history)
                generated = self._response_content(response)
            except Exception as exc:  # Ollama connection/model errors vary by client version.
                message = f"Ollama request failed: {type(exc).__name__}: {exc}"
                self._emit(on_event, events, message)
                return self._failure(message, str(destination), events, iteration)

            generated = self._sanitize(generated)
            inspection = inspect_python(generated)
            if not inspection["valid"]:
                last_result = {
                    "passed": False,
                    "stdout": "",
                    "stderr": inspection["error"],
                    "returncode": 2,
                }
            else:
                try:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_text(generated.rstrip() + "\n", encoding="utf-8")
                except OSError as exc:
                    message = f"Could not write generated tests to {destination}: {exc}"
                    self._emit(on_event, events, message)
                    return self._failure(message, str(destination), events, iteration)

                self._emit(on_event, events, f"Iteration {iteration}: running pytest (10 second timeout).")
                last_result = run_test(str(destination))

            if last_result["passed"]:
                self._emit(on_event, events, f"Iteration {iteration}: ✅ pytest passed.")
                return {
                    **last_result,
                    "passed": True,
                    "test_file": str(destination),
                    "iterations": iteration,
                    "retries": attempt,
                    "logs": list(events),
                    "error": "",
                }

            failure_output = "\n".join(
                part for part in (str(last_result.get("stdout", "")), str(last_result.get("stderr", ""))) if part
            ) or f"pytest exited with return code {last_result.get('returncode')} without output"
            if attempt == max_retries:
                self._emit(on_event, events, f"Iteration {iteration}: ❌ failed; maximum retries exhausted.")
                break

            summary = next(
                (line.strip() for line in failure_output.splitlines() if "AssertionError" in line or "Error" in line),
                failure_output.splitlines()[0].strip() if failure_output.splitlines() else "pytest failed",
            )
            self._emit(
                on_event,
                events,
                f"Iteration {iteration}: ❌ {summary}; feeding failure output back to the model.",
            )
            history.extend(
                [
                    {"role": "assistant", "content": generated},
                    {
                        "role": "user",
                        "content": (
                            "The generated tests did not pass. Fix the tests only, preserving their purpose. "
                            "Return the complete corrected pytest file as Python code, with no markdown fences.\n\n"
                            f"Raw pytest output / error traceback:\n{failure_output}"
                        ),
                    },
                ]
            )

        return {
            **last_result,
            "passed": False,
            "test_file": str(destination),
            "iterations": min(max_retries + 1, iteration),
            "retries": min(max_retries, iteration - 1),
            "logs": list(events),
            "error": "maximum retries exhausted",
        }

    @staticmethod
    def _response_content(response: Any) -> str:
        """Handle the mapping and object response shapes used by Ollama clients."""
        if isinstance(response, dict):
            message = response.get("message", {})
            content = message.get("content", "") if isinstance(message, dict) else ""
        else:
            message = getattr(response, "message", None)
            content = getattr(message, "content", "")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Ollama returned an empty response")
        return content

    @staticmethod
    def _validate_local_host(host: str) -> str:
        """Reject non-loopback Ollama endpoints so model traffic stays local."""
        try:
            parsed = urlparse(host if "://" in host else f"http://{host}")
            hostname = parsed.hostname
            if parsed.scheme not in {"http", "https"} or not hostname:
                raise ValueError
            try:
                is_loopback = ipaddress.ip_address(hostname).is_loopback
            except ValueError:
                is_loopback = hostname.lower() == "localhost"
            if not is_loopback:
                return "OLLAMA_HOST must point to a loopback address to keep model calls local"
        except (TypeError, ValueError):
            return "OLLAMA_HOST must be a valid local Ollama URL"
        return ""

    @staticmethod
    def _sanitize(code: str) -> str:
        """Remove a single surrounding Markdown code fence, if present."""
        stripped = code.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if lines and lines[0].strip().lower() in {"```", "```python", "```py"}:
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            stripped = "\n".join(lines).strip()
        return stripped

    @staticmethod
    def _emit(callback: ProgressCallback | None, events: list[str], message: str) -> None:
        events.append(message)
        if callback is not None:
            try:
                callback({"message": message, "logs": list(events)})
            except Exception:
                # A presentation callback must not break the testing workflow.
                pass

    @staticmethod
    def _failure(message: str, test_file: str, logs: list[str] | None = None, iterations: int = 0) -> dict[str, Any]:
        return {
            "passed": False,
            "stdout": "",
            "stderr": message,
            "returncode": -1,
            "test_file": test_file,
            "iterations": iterations,
            "retries": 0,
            "logs": list(logs or []),
            "error": message,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate and self-heal pytest tests with local Ollama.")
    parser.add_argument("--target", default="target_code.py", help="Python source file to test")
    parser.add_argument("--test-file", default="test_target.py", help="Path where generated tests are written")
    parser.add_argument("--max-retries", type=int, default=3, help="Number of model repair attempts")
    args = parser.parse_args()

    try:
        source = Path(args.target).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Could not read target source: {exc}")
        return 2

    result = TestForgeEngine().generate_and_heal(source, args.test_file, args.max_retries)
    for entry in result["logs"]:
        print(entry)
    if result["stdout"]:
        print(result["stdout"], end="" if str(result["stdout"]).endswith("\n") else "\n")
    if result["stderr"]:
        print(result["stderr"])
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
