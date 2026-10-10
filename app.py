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
CODE_WINDOW_HEIGHT = 360


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
        label[data-baseweb="checkbox"]:has(input:checked)>div:first-child{background:#146c6b!important;border-color:#146c6b!important}
        [data-testid="stCode"] {border:1px solid var(--line);border-radius:8px}
        .empty-state {background:#e9ede4;border:1px solid var(--line);border-radius:8px;padding:15px 16px;color:#58665e;font-size:13px;line-height:1.5;min-height:54px}
        [data-testid="stAlert"] {border-radius:8px;background:#e9ede4;border-color:var(--line)}
        [data-testid="stExpander"] {border:1px solid var(--line);border-radius:8px;background:var(--surface)}
        .footerline {border-top:1px solid var(--line);padding-top:14px;margin-top:2.2rem;color:#78837b;font-size:11px}
        @media(max-width:800px) {.workflow{grid-template-columns:repeat(2,1fr)}.workflow-step:nth-child(2){border-right:0}.workflow-step:nth-child(-n+2){border-bottom:1px solid var(--line)}}
        /* Workbench color and spacing overrides */
        :root {--ink:#182832;--muted:#687982;--paper:#edf1f3;--surface:#fff;--line:#d7e0e4;--forest:#146c6b;--lime:#b3d7ce}
        .stApp,[data-testid="stAppViewContainer"]{background:var(--paper);color:var(--ink)}
        [data-testid="stMainBlockContainer"]{max-width:1440px;padding:1rem 2rem 2.5rem}
        h1{font-size:1.75rem!important;line-height:1.2!important;letter-spacing:-.035em!important;font-weight:680!important}
        .brandbar{padding-bottom:.8rem;margin-bottom:1.2rem}
        .brand-mark{background:#1d3941;color:#e4f2ef}
        .runtime-card{display:flex;align-items:center;justify-content:flex-end;gap:7px;flex-wrap:wrap;background:transparent;border:0;padding:0;margin:0}
        .runtime-kicker,.runtime-model,.runtime-endpoint{display:none}
        .status-chip{display:inline-flex;align-items:center;gap:7px;border:1px solid var(--line);background:#fff;border-radius:999px;padding:6px 10px;font-size:11px}
        .status-label{color:#53656e}.status-value{display:none}
        .is-ready .status-led{background:#21856c;box-shadow:0 0 0 3px #e1f1e9}
        .is-missing .status-led{background:#bd715d;box-shadow:0 0 0 3px #f7e8e3}
        .hero-copy{font-size:13px;margin:0 0 1.1rem}.hero-note{display:none}
        .section-rule{margin:1rem 0 .6rem;color:#40545d;font-size:12px;letter-spacing:.02em}
        .workspace-intro{margin:.2rem 0 .6rem}
        [data-testid="stHorizontalBlock"] [data-testid="column"]:has(.panel-heading){background:#fff;border:1px solid var(--line);border-radius:11px;padding:1rem 1rem .65rem;box-shadow:0 1px 2px rgba(24,40,50,.04)}
        .panel-heading{border-color:var(--line);padding-bottom:10px;margin-bottom:10px}
        .panel-title{font-size:12px;font-weight:750;color:#30434c}
        .panel-tag{color:#70818a;font-size:11px}
        .support-note{font-size:11px;margin:7px 0 1px}
        .empty-state{background:#f3f7f7;border:1px dashed #c6d4d8;color:#62757d}
        [data-testid="stCode"]{border:1px solid #d2dcdf;border-radius:8px;overflow:hidden}
        .stButton>button[kind="primary"]{background:#146c6b;border-color:#146c6b;border-radius:7px;min-height:40px;font-weight:650}
        .stButton>button[kind="primary"]:hover{background:#0f5c5c;border-color:#0f5c5c}
        [data-testid="stAlert"]{border-radius:8px;background:#f7f9f8;border-color:var(--line)}
        [data-testid="stFileUploader"] section{background:#f7f9f8;border:1px dashed #c4d1d5;border-radius:8px}
        .page-subtitle,.run-meta{color:var(--muted);font-size:12px;line-height:1.5}
        @media(max-width:800px){[data-testid="stMainBlockContainer"]{padding-left:1rem;padding-right:1rem}.runtime-card{justify-content:flex-start}.brand-meta{display:none}[data-testid="stHorizontalBlock"]:has(.panel-heading){flex-wrap:wrap}[data-testid="stHorizontalBlock"]:has(.panel-heading)>[data-testid="column"]{flex:1 1 100%;min-width:100%}}
        /* VS Code-inspired editor shell */
        :root{--ink:#d4d4d4;--muted:#969da3;--paper:#1e1e1e;--surface:#252526;--line:#38383b;--forest:#0e639c;--lime:#3794ff}
        .stApp,[data-testid="stAppViewContainer"]{background:#1e1e1e;color:#d4d4d4}
        [data-testid="stMainBlockContainer"]{max-width:none;padding:0 1.2rem 1.5rem}
        h1,h2,h3,p,label{color:#d4d4d4}
        [data-testid="stMarkdownContainer"] p{color:#9da3a9}
        .brandbar{height:45px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #303033;margin:0 -1.2rem 1rem;padding:0 1.2rem;background:#181818}
        .brand-mark{display:grid;place-items:center;width:23px;height:23px;border-radius:5px;background:#245d67;color:#e3f6f3;font-size:10px}
        .brand-name{font-size:13px;letter-spacing:0;color:#e5e5e5}
        .brand-sub{font-size:11px;color:#858b91;letter-spacing:0}
        .brand-meta{font:11px ui-monospace,SFMono-Regular,Menlo,monospace;color:#9da4aa}
        h1{font-size:15px!important;line-height:1.4!important;letter-spacing:.04em!important;text-transform:uppercase;color:#aeb4ba!important;margin:0 0 .5rem!important}
        .page-subtitle{display:none}
        .runtime-card{display:flex;gap:6px;justify-content:flex-start;margin:0 0 .6rem}
        .status-chip{display:inline-flex;align-items:center;gap:6px;padding:4px 8px;background:#252526;border:1px solid #3b3b3b;border-radius:4px;font-size:10px}
        .status-label{color:#b8bec4}.status-value{display:none}
        .is-ready .status-led{background:#4ec9b0;box-shadow:none}.is-missing .status-led{background:#f48771;box-shadow:none}
        [data-testid="stHorizontalBlock"]{gap:.65rem}
        .panel-heading{display:flex;align-items:center;gap:8px;background:#252526;height:36px;padding:0 12px;border:1px solid #38383b;border-bottom:0;border-radius:5px 5px 0 0;margin:0;color:#d7d7d7}
        .panel-title{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;color:#d7d7d7}
        .panel-tag{margin-left:auto;color:#868c92;font:10px ui-monospace,SFMono-Regular,Menlo,monospace}
        [data-testid="stCode"]{border:1px solid #38383b;border-radius:0 0 5px 5px;overflow:hidden;margin-top:0}
        [data-testid="stCode"] pre{background:#1b1b1c!important}
        .empty-state{height:360px;display:flex;align-items:center;justify-content:center;background:#1b1b1c;border:1px solid #38383b;border-radius:0 0 5px 5px;color:#7c8288}
        .stButton>button[kind="primary"]{background:#0e639c;color:#fff;border:1px solid #1177bb;border-radius:4px;min-height:34px;font-size:12px;font-weight:600}
        .stButton>button[kind="primary"]:hover{background:#1177bb;border-color:#2898e0;color:#fff}
        .stButton>button:disabled{background:#333;border-color:#414141;color:#777}
        label[data-baseweb="checkbox"]:has(input:checked)>div:first-child{background:#0e639c!important;border-color:#0e639c!important}
        [data-testid="stWidgetLabel"] p{color:#c6c6c6!important;font-size:12px}
        [data-testid="stFileUploader"] section{background:#202124;border:1px dashed #4a4d50;border-radius:4px}
        [data-testid="stFileUploader"] section *{color:#c4c4c4!important}
        [data-testid="stAlert"]{background:#332b24;border:1px solid #6e5535;color:#e5c68b}
        [data-testid="stExpander"]{background:#252526;border:1px solid #38383b;border-radius:4px}
        .run-row{border-top:1px solid #38383b;margin-top:.8rem;padding-top:.7rem}
        .activity-heading{display:flex;align-items:center;gap:15px;background:#252526;border:1px solid #38383b;border-bottom:0;padding:8px 12px;color:#aaa;font-size:10px;letter-spacing:.03em}
        .activity-heading .selected{border-bottom:1px solid #3794ff;padding-bottom:8px;margin-bottom:-9px;color:#fff}
        .statusbar{display:flex;align-items:center;gap:17px;background:#007acc;color:#fff;margin:1rem -1.2rem -1.5rem;padding:4px 12px;font-size:10px}
        .statusbar span:last-child{margin-left:auto}
        @media(max-width:760px){[data-testid="stMainBlockContainer"]{padding-left:.7rem;padding-right:.7rem}.brandbar{margin-left:-.7rem;margin-right:-.7rem;padding:0 .7rem}[data-testid="stHorizontalBlock"]:has(.panel-heading){flex-direction:row!important;flex-wrap:nowrap!important}[data-testid="stHorizontalBlock"]:has(.panel-heading)>[data-testid="column"]{flex:1 1 0%!important;min-width:0!important}.statusbar{margin-left:-.7rem;margin-right:-.7rem}}
        @media(max-width:520px){[data-testid="stHorizontalBlock"]:has(.panel-heading){flex-direction:column!important}[data-testid="stHorizontalBlock"]:has(.panel-heading)>[data-testid="column"]{flex:1 1 100%!important;min-width:100%!important}}
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
        '<div><span class="brand-name">OPEN TEST</span><span class="brand-sub">LOCAL TEST RUNNER</span></div></div>'
        '<div class="brand-meta">Private by design · Runs on your machine</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<h1>Test workspace</h1><div class="page-subtitle">Choose a built-in example or upload a Python module to begin.</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="runtime-card">'
        f'{_status_chip("Ollama", status["ollama"])}'
        f'{_status_chip(MODEL, status["model"])}'
        f'{_status_chip("Pytest", status["pytest"] and status["ollama_package"])}</div>',
        unsafe_allow_html=True,
    )

    source: str | None = None
    source_name = ""
    source_error: str | None = None
    is_demo = True
    source_inspection: dict[str, Any] = {"valid": False, "error": ""}
    mode_col, upload_col = st.columns([.55, 1.45], vertical_alignment="center")
    with mode_col:
        is_demo = st.toggle(
            "Demo mode",
            value=True,
            help="Loads target_code.py automatically for a repeatable walkthrough.",
        )
    if is_demo:
        source, source_name, source_error = _load_demo_source()
    else:
        with upload_col:
            uploaded_file = st.file_uploader(
                "Target module",
                type=["py"],
                help="The uploaded file is isolated to this run.",
            )
            source, source_name, source_error = _load_upload(uploaded_file)

    source_inspection = inspect_python(source) if source else {"valid": False, "error": ""}
    if source and not source_inspection["valid"]:
        source_error = source_inspection["error"]

    source_col, output_col = st.columns([1, 1], gap="large")
    with source_col:
        escaped_name = html.escape(source_name or ("Choose a .py file" if not is_demo else "target_code.py"))
        source_label = "Demo target" if is_demo else "Uploaded target"
        st.markdown(
            f'<div class="panel-heading"><span class="panel-title">{source_label}</span>'
            f'<span class="panel-tag">{escaped_name}</span></div>',
            unsafe_allow_html=True,
        )
        if source:
            st.code(source, language="python", line_numbers=True, height=CODE_WINDOW_HEIGHT)
            st.markdown('<div class="support-note">Read-only preview · Isolated copy per run.</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="empty-state">Choose a <code>.py</code> file to preview it here and enable a run.</div>',
                unsafe_allow_html=True,
            )
        if source_error:
            st.error(source_error)

    last_test_path = st.session_state.get("generated_test_path")
    with output_col:
        st.markdown(
            '<div class="panel-heading"><span class="panel-title">Tests</span>'
            '<span class="panel-tag">test_target.py</span></div>',
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
        st.markdown('<div class="support-note">Repairs alter generated tests only.</div>', unsafe_allow_html=True)

    ready = bool(status["ollama"] and status["model"] and status["pytest"] and status["ollama_package"])
    target_ready = bool(source and source_inspection["valid"] and not source_error)
    st.markdown('<div class="run-row"></div>', unsafe_allow_html=True)
    run_col, help_col = st.columns([.38, 1.62], vertical_alignment="center")
    with run_col:
        run_clicked = st.button("▶  Run tests", type="primary", disabled=not (ready and target_ready), use_container_width=True)
    with help_col:
        st.markdown('<div class="run-meta">One draft, up to three repairs · Each pytest run is capped at 10 seconds</div>', unsafe_allow_html=True)
        if not ready:
            instructions = _install_instructions(status)
            if instructions:
                st.info("\n\n".join(instructions))
        elif not target_ready and not source_error:
            st.caption("Choose a Python module to enable a run.")

    st.markdown('<div class="activity-heading"><span class="selected">TERMINAL</span><span>OUTPUT</span><span>PROBLEMS</span><span style="margin-left:auto">RUN ACTIVITY</span></div>', unsafe_allow_html=True)
    log_placeholder = st.empty()
    saved_logs = st.session_state.get("run_logs", [])
    if saved_logs:
        log_placeholder.code("\n".join(saved_logs), language="text", height=150)
    else:
        st.markdown('<div class="empty-state" style="height:auto;min-height:50px;justify-content:flex-start;padding:14px">No activity yet. Run tests to see model and pytest output.</div>', unsafe_allow_html=True)

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
                log_placeholder.code("\n".join(entries), language="text", height=150)

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

    st.markdown('<div class="statusbar"><span>Open Test</span><span>Python</span><span>pytest · 10s timeout</span><span>Local model: qwen2.5-coder:3b</span></div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
