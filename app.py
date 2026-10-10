"""Streamlit showcase for the local-first Open Test harness."""

from __future__ import annotations

import html
import importlib.util
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4

import streamlit as st

from harness.ast_inspector import inspect_python
from harness.generator import TestForgeEngine


ROOT = Path(__file__).resolve().parent
TARGET_FILE = ROOT / "target_code.py"
RUNS_DIR = ROOT / ".open_test_runs"
MODEL = "qwen2.5-coder:3b"
OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"
CODE_WINDOW_HEIGHT = 380


def _runtime_status() -> dict[str, Any]:
    """Check only local runtime prerequisites; this does not contact the internet."""
    status: dict[str, Any] = {
        "ollama": False,
        "model": False,
        "pytest": importlib.util.find_spec("pytest") is not None,
        "ollama_package": importlib.util.find_spec("ollama") is not None,
    }
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(OLLAMA_TAGS_URL, timeout=0.6) as response:
            payload = json.loads(response.read().decode("utf-8"))
        names = [item.get("name", "") for item in payload.get("models", []) if isinstance(item, dict)]
        status["ollama"] = True
        status["model"] = any(name == MODEL or name.startswith(f"{MODEL}:") for name in names)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        pass
    return status


def _status_chip(label: str, ready: bool) -> str:
    state_class = "is-ready" if ready else "is-missing"
    state_text = "Ready" if ready else "Needs setup"
    return (
        f'<div class="status-chip {state_class}"><span class="status-led"></span>'
        f'<span class="status-label">{label}</span><span class="status-value">{state_text}</span></div>'
    )


def _install_instructions(status: dict[str, Any]) -> list[str]:
    steps: list[str] = []
    if not status["pytest"] or not status["ollama_package"]:
        steps.append("Install dependencies with `python -m pip install -r requirements.txt`.")
    if not status["ollama"]:
        steps.append("Start Ollama, then pull `qwen2.5-coder:3b`.")
    elif not status["model"]:
        steps.append("Pull the required model with `ollama pull qwen2.5-coder:3b`.")
    return steps


def _load_demo_source() -> tuple[str | None, str, str | None]:
    try:
        return TARGET_FILE.read_text(encoding="utf-8"), TARGET_FILE.name, None
    except OSError as exc:
        return None, TARGET_FILE.name, f"Could not read {TARGET_FILE.name}: {exc}"


def _load_upload(upload: Any) -> tuple[str | None, str, str | None]:
    if upload is None:
        return None, "", None
    name = Path(upload.name).name
    try:
        source = upload.getvalue().decode("utf-8-sig")
    except UnicodeDecodeError:
        return None, name, "This file is not valid UTF-8 Python source."
    if not source.strip():
        return None, name, "The uploaded Python file is empty."
    return source, name, None


def _new_run_files(source: str) -> Path:
    """Create an isolated per-run module and test path without overwriting demo code."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_dir = RUNS_DIR / uuid4().hex
    run_dir.mkdir()
    (run_dir / "target_code.py").write_text(source, encoding="utf-8")
    return run_dir / "test_target.py"


def _render_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --ink:#1c2721; --muted:#68746d; --paper:#f3f4ef; --surface:#fbfcf8;
            --line:#dce1d8; --forest:#244a39; --lime:#c8ee76;
        }
        .stApp,[data-testid="stAppViewContainer"] {background:var(--paper);color:var(--ink)}
        [data-testid="stHeader"] {background:transparent}
        [data-testid="stMainBlockContainer"] {max-width:1380px;padding-top:1rem;padding-bottom:3.5rem}
        h1,h2,h3,p,label {color:var(--ink)}
        h1 {font-size:clamp(2.7rem,5vw,4.7rem)!important;line-height:.99!important;letter-spacing:-.065em!important;font-weight:650!important}
        h2 {letter-spacing:-.04em!important;font-weight:630!important}
        [data-testid="stMarkdownContainer"] p {color:var(--muted)}
        .brandbar {display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line);padding:0 0 1rem;margin-bottom:2.35rem}
        .brand-lockup {display:flex;align-items:center;gap:.7rem;color:var(--ink)}
        .brand-mark {display:grid;place-items:center;width:34px;height:34px;border-radius:8px;background:var(--forest);color:#eff8d8;font-size:12px;font-weight:800;letter-spacing:-.06em}
        .brand-name {font-size:13px;font-weight:800;letter-spacing:.08em}
        .brand-sub {color:var(--muted);font-size:11px;margin-left:.5rem}
        .brand-meta {color:var(--muted);font-size:12px}
        .eyebrow {font-size:12px;color:var(--forest);font-weight:700;margin-bottom:.9rem}
        .hero-copy {max-width:680px;color:#58665e;font-size:17px;line-height:1.6;margin-top:1.1rem}
        .hero-note {border-left:2px solid var(--lime);padding:1px 0 1px 16px;margin-top:1.5rem;color:var(--muted);font-size:13px;line-height:1.55}
        .runtime-card {background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:1.25rem;margin-top:.4rem}
        .runtime-kicker {color:var(--muted);font-size:11px;font-weight:700}
        .runtime-model {color:var(--ink);font-size:18px;font-weight:700;letter-spacing:-.03em;margin:.55rem 0 .2rem}
        .runtime-endpoint {color:var(--muted);font-size:12px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;margin-bottom:1.1rem}
        .status-chip {display:flex;align-items:center;gap:9px;border-top:1px solid #e8ebe4;padding:9px 0 2px;font-size:12px}
        .status-led {width:7px;height:7px;border-radius:50%;background:#bdc5bc;flex:0 0 auto}
        .is-ready .status-led {background:#58865e;box-shadow:0 0 0 3px #e5f0df}
        .is-missing .status-led {background:#bb675a;box-shadow:0 0 0 3px #f4e8e4}
        .status-label {color:#59675e;flex:1}
        .status-value {font-size:11px;color:#747f77}
        .is-ready .status-value {color:#46724d}
        .section-rule {display:flex;align-items:center;gap:13px;margin:2.5rem 0 1rem;color:#66736a;font-size:12px;font-weight:700}
        .section-rule:after {content:'';height:1px;background:var(--line);flex:1}
        .workflow {display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
        .workflow-step {padding:14px 16px 15px;min-height:70px;border-right:1px solid var(--line)}
        .workflow-step:first-child {padding-left:0}
        .workflow-step:last-child {border:0}
        .step-num {display:block;color:#7c887f;font-size:10px;margin-bottom:7px}
        .step-name {color:var(--ink);font-size:13px;font-weight:650}
        .workspace-intro {margin-top:-.4rem;margin-bottom:1rem;color:var(--muted);font-size:13px}
        .panel-heading {display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line);padding-bottom:11px;margin-bottom:12px}
        .panel-title {font-size:12px;font-weight:750;color:#39473e}
        .panel-tag {color:#7c887f;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11px}
        .support-note {color:var(--muted);font-size:12px;line-height:1.55;margin:8px 0 15px}
        .result-strip {display:flex;flex-wrap:wrap;gap:7px;margin:12px 0 0}
        .result-pill {border:1px solid var(--line);border-radius:999px;padding:5px 9px;color:#526057;font-size:10px;background:var(--surface)}
        .stButton>button[kind="primary"] {background:var(--forest);color:white;border:1px solid var(--forest);border-radius:7px;min-height:43px;font-weight:700}
        .stButton>button[kind="primary"]:hover {background:#315e49;border-color:#315e49;color:white}
        .stButton>button:disabled {background:#dfe4dc;color:#879188;border:1px solid #dfe4dc}
        [data-testid="stCode"] {border:1px solid var(--line);border-radius:8px}
        .empty-state {background:#e9ede4;border:1px solid var(--line);border-radius:8px;padding:15px 16px;color:#58665e;font-size:13px;line-height:1.5;min-height:54px}
        [data-testid="stAlert"] {border-radius:8px;background:#e9ede4;border-color:var(--line)}
        [data-testid="stExpander"] {border:1px solid var(--line);border-radius:8px;background:var(--surface)}
        .footerline {border-top:1px solid var(--line);padding-top:14px;margin-top:2.2rem;color:#78837b;font-size:11px}
        @media(max-width:800px) {.workflow{grid-template-columns:repeat(2,1fr)}.workflow-step:nth-child(2){border-right:0}.workflow-step:nth-child(-n+2){border-bottom:1px solid var(--line)}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="Open Test — Local Test Forge", page_icon="🧪", layout="wide")
    _render_styles()
    status = _runtime_status()

    st.markdown(
        '<div class="brandbar"><div class="brand-lockup"><div class="brand-mark">OT</div>'
        '<div><span class="brand-name">OPEN TEST</span><span class="brand-sub">A LOCAL PYTEST WORKSPACE</span></div></div>'
        '<div class="brand-meta">Private by design · Runs on your machine</div></div>',
        unsafe_allow_html=True,
    )

    hero, runtime = st.columns([1.55, 0.8], gap="large", vertical_alignment="center")
    with hero:
        st.markdown('<div class="eyebrow">Write tests. Run them. Learn from failures.</div>', unsafe_allow_html=True)
        st.markdown('<h1>Tests for your code.<br>Repairs from real failures.</h1>', unsafe_allow_html=True)
        st.markdown(
            '<div class="hero-copy">Open Test uses a local coding model to draft pytest coverage, '
            'runs it with a strict time limit, and feeds the failure output back for another pass.</div>'
            '<div class="hero-note">Source files, generated tests, and tracebacks stay on this machine. '
            'The model connection is restricted to local Ollama.</div>',
            unsafe_allow_html=True,
        )
    with runtime:
        st.markdown(
            f'<div class="runtime-card"><div class="runtime-kicker">Local engine</div>'
            f'<div class="runtime-model">{MODEL}</div><div class="runtime-endpoint">127.0.0.1:11434</div>'
            f'{_status_chip("Ollama service", status["ollama"])}'
            f'{_status_chip("Model downloaded", status["model"])}'
            f'{_status_chip("Python dependencies", status["pytest"] and status["ollama_package"])}</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-rule">How a run works</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="workflow">'
        '<div class="workflow-step"><span class="step-num">01 · SOURCE</span><span class="step-name">Read your Python module</span></div>'
        '<div class="workflow-step"><span class="step-num">02 · DRAFT</span><span class="step-name">Generate focused tests</span></div>'
        '<div class="workflow-step"><span class="step-num">03 · RUN</span><span class="step-name">Execute with a 10s cap</span></div>'
        '<div class="workflow-step"><span class="step-num">04 · REPAIR</span><span class="step-name">Use failures for the next pass</span></div>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-rule">Workspace</div>', unsafe_allow_html=True)
    st.markdown('<div class="workspace-intro">Choose the built-in walkthrough or bring a Python module of your own.</div>', unsafe_allow_html=True)

    source_col, output_col = st.columns([1, 1], gap="large")
    source: str | None = None
    source_name = ""
    source_error: str | None = None
    is_demo = True
    source_inspection: dict[str, Any] = {"valid": False, "error": ""}
    with source_col:
        is_demo = st.toggle(
            "Demo mode",
            value=True,
            help="Loads target_code.py automatically for a repeatable walkthrough.",
        )
        if is_demo:
            source, source_name, source_error = _load_demo_source()
        else:
            uploaded_file = st.file_uploader(
                "Upload a Python module",
                type=["py"],
                help="The uploaded file is isolated to this run.",
            )
            source, source_name, source_error = _load_upload(uploaded_file)

        source_inspection = inspect_python(source) if source else {"valid": False, "error": ""}
        if source and not source_inspection["valid"]:
            source_error = source_inspection["error"]

        escaped_name = html.escape(source_name or ("Choose a .py file" if not is_demo else "target_code.py"))
        source_label = "Demo target" if is_demo else "Uploaded target"
        st.markdown(
            f'<div class="panel-heading"><span class="panel-title">{source_label}</span>'
            f'<span class="panel-tag">{escaped_name}</span></div>',
            unsafe_allow_html=True,
        )
        if source:
            st.code(source, language="python", line_numbers=True, height=CODE_WINDOW_HEIGHT)
            st.markdown(
                '<div class="support-note">This read-only preview has its own scroll area. '
                'Uploaded source is copied into a per-run workspace before pytest starts.</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="empty-state">Choose a <code>.py</code> file to preview it here and enable a run.</div>',
                unsafe_allow_html=True,
            )
        if source_error:
            st.error(source_error)

    last_test_path = st.session_state.get("generated_test_path")
    last_source_name = st.session_state.get("generated_source_name", "")
    with output_col:
        output_caption = f"from {html.escape(last_source_name)}" if last_test_path and last_source_name else "awaiting first run"
        st.markdown(
            '<div class="panel-heading"><span class="panel-title">Generated tests</span>'
            f'<span class="panel-tag">test_target.py · {output_caption}</span></div>',
            unsafe_allow_html=True,
        )
        if last_test_path and Path(last_test_path).is_file():
            try:
                generated = Path(last_test_path).read_text(encoding="utf-8")
            except OSError as exc:
                st.error(f"Could not read generated tests: {exc}")
            else:
                st.code(generated, language="python", line_numbers=True, height=CODE_WINDOW_HEIGHT)
        else:
            st.markdown(
                '<div class="empty-state">Generated tests will appear here after the first run.</div>',
                unsafe_allow_html=True,
            )
        st.markdown(
            '<div class="support-note">The repair loop changes generated tests only; it never rewrites your module.</div>',
            unsafe_allow_html=True,
        )

    run_col, log_col = st.columns([0.78, 1.22], gap="large", vertical_alignment="top")
    ready = bool(status["ollama"] and status["model"] and status["pytest"] and status["ollama_package"])
    target_ready = bool(source and source_inspection["valid"] and not source_error)
    with run_col:
        st.markdown('<div class="panel-title">Run tests</div>', unsafe_allow_html=True)
        st.caption("One draft, then up to three repairs. Each pytest run stops after 10 seconds.")
        run_clicked = st.button(
            "Generate and run tests",
            type="primary",
            disabled=not (ready and target_ready),
            use_container_width=True,
        )
        if not ready:
            instructions = _install_instructions(status)
            if instructions:
                st.info("\n\n".join(instructions))
        elif not target_ready and not source_error:
            st.caption("Upload a `.py` file to start a run.")
        st.markdown(
            '<div class="result-strip"><span class="result-pill">LOCAL MODEL</span>'
            '<span class="result-pill">NO REMOTE API</span><span class="result-pill">3 REPAIRS</span></div>',
            unsafe_allow_html=True,
        )

    with log_col:
        st.markdown(
            '<div class="panel-heading"><span class="panel-title">Run activity</span>'
            '<span class="panel-tag">iteration trace</span></div>',
            unsafe_allow_html=True,
        )
        log_placeholder = st.empty()
        saved_logs = st.session_state.get("run_logs", [])
        if saved_logs:
            log_placeholder.code("\n".join(saved_logs), language="text", height=180)
        else:
            log_placeholder.caption("Model requests, pytest output, and repair steps will appear here.")

        if run_clicked and source:
            st.session_state["run_logs"] = []
            try:
                test_path = _new_run_files(source)
            except OSError as exc:
                st.error(f"Could not prepare an isolated run folder: {exc}")
            else:
                st.session_state["generated_test_path"] = str(test_path)
                st.session_state["generated_source_name"] = source_name

                def show_event(event: dict[str, Any]) -> None:
                    entries = list(event.get("logs", []))
                    st.session_state["run_logs"] = entries
                    log_placeholder.code("\n".join(entries), language="text", height=180)

                with st.spinner("Generating and executing locally…"):
                    result = TestForgeEngine(model=MODEL).generate_and_heal(
                        source,
                        str(test_path),
                        max_retries=3,
                        on_event=show_event,
                    )
                st.session_state["last_result"] = result
                st.session_state["run_logs"] = result.get("logs", [])
                st.rerun()

    previous = st.session_state.get("last_result")
    if previous:
        if previous["passed"]:
            st.success(f"Verified — pytest passed in {previous['iterations']} iteration(s).")
        else:
            st.error(previous.get("error") or "The run did not pass.")
        with st.expander("Execution details", expanded=False):
            st.write(
                f"Status: {'passed' if previous['passed'] else 'failed'} · "
                f"Iterations: {previous.get('iterations', 0)} · "
                f"Return code: {previous.get('returncode', -1)}"
            )
            if previous.get("stdout"):
                st.code(previous["stdout"], language="text", height=220)
            if previous.get("stderr"):
                st.code(previous["stderr"], language="text", height=150)

    st.markdown(
        '<div class="footerline">OPEN TEST · PYTEST EXECUTION HARNESS · SOURCE AND MODEL TRAFFIC STAY LOCAL</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
