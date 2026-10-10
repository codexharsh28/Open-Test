"""Streamlit showcase for the local-first Open Test harness."""

from __future__ import annotations

import importlib.util
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import streamlit as st

from harness.generator import TestForgeEngine


ROOT = Path(__file__).resolve().parent
TARGET_FILE = ROOT / "target_code.py"
GENERATED_FILE = ROOT / "test_target.py"
MODEL = "qwen2.5-coder:3b"
OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"


def _runtime_status() -> dict[str, Any]:
    """Check only local runtime prerequisites; this does not contact the internet."""
    status: dict[str, Any] = {
        "ollama": False,
        "model": False,
        "model_names": [],
        "pytest": importlib.util.find_spec("pytest") is not None,
        "ollama_package": importlib.util.find_spec("ollama") is not None,
    }
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(OLLAMA_TAGS_URL, timeout=0.6) as response:
            payload = json.loads(response.read().decode("utf-8"))
        names = [item.get("name", "") for item in payload.get("models", []) if isinstance(item, dict)]
        status["ollama"] = True
        status["model_names"] = names
        status["model"] = any(name == MODEL or name.startswith(f"{MODEL}:") for name in names)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        pass
    return status


def _status_chip(label: str, ready: bool) -> str:
    state_class = "is-ready" if ready else "is-missing"
    state_text = "READY" if ready else "SETUP NEEDED"
    return (
        f'<div class="status-chip {state_class}"><span class="status-led"></span>'
        f'<span class="status-label">{label}</span><span class="status-value">{state_text}</span></div>'
    )


def _install_instructions(status: dict[str, Any]) -> list[str]:
    steps: list[str] = []
    if not status["pytest"] or not status["ollama_package"]:
        steps.append("Install Python dependencies: `python -m pip install -r requirements.txt`")
    if not status["ollama"]:
        steps.append("Start the local Ollama service, then pull the model: `ollama pull qwen2.5-coder:3b`")
    elif not status["model"]:
        steps.append("Pull the required local model: `ollama pull qwen2.5-coder:3b`")
    return steps


def main() -> None:
    st.set_page_config(page_title="Open Test — Local Test Forge", page_icon="🧪", layout="wide")
    st.markdown(
        """
        <style>
        :root {
            --ink: #19211d;
            --muted: #64716a;
            --paper: #f3f4ef;
            --surface: #fbfcf8;
            --line: #dce1d8;
            --forest: #244a39;
            --lime: #c8ee76;
            --red: #b74d40;
        }
        .stApp { background: var(--paper); color: var(--ink); }
        [data-testid="stAppViewContainer"] { background: var(--paper); }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stMainBlockContainer"] { max-width: 1440px; padding-top: 1.2rem; padding-bottom: 4rem; }
        h1, h2, h3, p, label { color: var(--ink); }
        h1 { font-size: clamp(2.8rem, 5vw, 5rem) !important; line-height: .98 !important; letter-spacing: -.065em !important; font-weight: 650 !important; }
        h2 { letter-spacing: -.045em !important; font-weight: 620 !important; }
        h3 { letter-spacing: -.025em !important; font-weight: 620 !important; }
        [data-testid="stMarkdownContainer"] p { color: var(--muted); }
        .brandbar { display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid var(--line); padding: 0 0 1.1rem; margin-bottom:2.6rem; }
        .brand-lockup { display:flex; align-items:center; gap:.75rem; color:var(--ink); }
        .brand-mark { display:grid; place-items:center; width:34px; height:34px; border-radius:9px; background:var(--forest); color:#eff8d8; font-size:12px; font-weight:800; letter-spacing:-.06em; }
        .brand-name { font-size:13px; font-weight:800; letter-spacing:.10em; }
        .brand-sub { color:var(--muted); font-size:10px; letter-spacing:.13em; margin-left:.45rem; }
        .brand-meta { color:var(--muted); font-size:11px; letter-spacing:.11em; text-transform:uppercase; }
        .eyebrow { display:flex; align-items:center; gap:.55rem; font-size:11px; line-height:1.2; text-transform:uppercase; letter-spacing:.18em; font-weight:750; color:var(--forest); margin-bottom:1.1rem; }
        .eyebrow:before { content:''; width:19px; height:2px; background:var(--forest); display:inline-block; }
        .hero-copy { max-width:720px; color:#58665e; font-size:17px; line-height:1.65; margin-top:1.25rem; }
        .hero-note { border-left:2px solid var(--lime); padding:1px 0 1px 18px; margin-top:1.8rem; color:var(--muted); font-size:13px; line-height:1.6; }
        .runtime-card { background:var(--surface); border:1px solid var(--line); border-radius:14px; padding:1.35rem; margin-top:.4rem; }
        .runtime-kicker { color:var(--muted); font-size:10px; letter-spacing:.17em; text-transform:uppercase; font-weight:750; }
        .runtime-model { color:var(--ink); font-size:18px; font-weight:700; letter-spacing:-.03em; margin:.55rem 0 .25rem; }
        .runtime-endpoint { color:var(--muted); font-size:12px; font-family:ui-monospace, SFMono-Regular, Menlo, monospace; margin-bottom:1.2rem; }
        .status-chip { display:flex; align-items:center; gap:8px; border-top:1px solid #e8ebe4; padding:10px 0 2px; font-size:10px; letter-spacing:.08em; }
        .status-led { width:7px; height:7px; border-radius:50%; background:#bdc5bc; flex:0 0 auto; }
        .is-ready .status-led { background:#58865e; box-shadow:0 0 0 3px #e5f0df; }
        .is-missing .status-led { background:#bb675a; box-shadow:0 0 0 3px #f4e8e4; }
        .status-label { color:#69756d; flex:1; }
        .status-value { font-size:9px; font-weight:800; color:#6b756e; }
        .is-ready .status-value { color:#46724d; }
        .section-rule { display:flex; align-items:center; gap:12px; margin:2.9rem 0 1.1rem; color:#758078; font-size:10px; font-weight:750; letter-spacing:.17em; text-transform:uppercase; }
        .section-rule:after { content:''; height:1px; background:var(--line); flex:1; }
        .workflow { display:grid; grid-template-columns:repeat(4,1fr); background:var(--surface); border:1px solid var(--line); border-radius:12px; overflow:hidden; }
        .workflow-step { padding:17px 19px 18px; min-height:79px; border-right:1px solid var(--line); }
        .workflow-step:last-child { border:0; }
        .step-num { display:block; color:#8c978f; font-size:9px; letter-spacing:.16em; margin-bottom:8px; }
        .step-name { color:var(--ink); font-size:13px; font-weight:670; }
        .workspace-intro { margin-top:-.55rem; margin-bottom:1rem; color:var(--muted); font-size:13px; }
        .panel-heading { display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid var(--line); padding-bottom:12px; margin-bottom:13px; }
        .panel-title { font-size:12px; text-transform:uppercase; letter-spacing:.13em; font-weight:800; color:#39473e; }
        .panel-tag { color:#7c887f; font-family:ui-monospace, SFMono-Regular, Menlo, monospace; font-size:10px; }
        .support-card { background:#e9ede4; border-radius:10px; padding:14px 16px; color:#536057; font-size:12px; line-height:1.55; margin:12px 0 18px; }
        .support-card strong { color:var(--ink); }
        .result-strip { display:flex; flex-wrap:wrap; gap:8px; margin:12px 0 0; }
        .result-pill { border:1px solid var(--line); border-radius:999px; padding:6px 10px; color:#526057; font-size:10px; letter-spacing:.06em; background:#fbfcf8; }
        .stButton > button[kind="primary"] { background:var(--forest); color:white; border:1px solid var(--forest); border-radius:8px; min-height:45px; font-weight:700; }
        .stButton > button[kind="primary"]:hover { background:#315e49; border-color:#315e49; color:white; }
        .stButton > button:disabled { background:#dfe4dc; color:#879188; border:1px solid #dfe4dc; }
        [data-testid="stCode"] { border:1px solid var(--line); border-radius:9px; }
        [data-testid="stAlert"] { border-radius:9px; }
        [data-testid="stExpander"] { border:1px solid var(--line); border-radius:9px; background:var(--surface); }
        .footerline { border-top:1px solid var(--line); padding-top:15px; margin-top:2.5rem; color:#78837b; font-size:10px; letter-spacing:.08em; }
        @media (max-width: 800px) { .workflow { grid-template-columns:repeat(2,1fr); } .workflow-step:nth-child(2) { border-right:0; } .workflow-step:nth-child(-n+2) { border-bottom:1px solid var(--line); } }
        </style>
        """,
        unsafe_allow_html=True,
    )

    status = _runtime_status()
    st.markdown(
        '<div class="brandbar"><div class="brand-lockup"><div class="brand-mark">OT</div>'
        '<div><span class="brand-name">OPEN TEST</span><span class="brand-sub">LOCAL TEST FORGE</span></div></div>'
        '<div class="brand-meta">Private by design &nbsp;·&nbsp; Runs on your machine</div></div>',
        unsafe_allow_html=True,
    )

    hero, runtime = st.columns([1.55, 0.8], gap="large", vertical_alignment="center")
    with hero:
        st.markdown('<div class="eyebrow">A self-healing test harness</div>', unsafe_allow_html=True)
        st.markdown('<h1>Make failures<br>make progress.</h1>', unsafe_allow_html=True)
        st.markdown(
            '<div class="hero-copy">Open Test asks a local coding model to write pytest coverage, '
            'runs it under a strict time limit, then gives real failure output back for another pass.</div>'
            '<div class="hero-note">Your source, generated tests, and tracebacks stay on this machine. '
            'The model connection is restricted to the local Ollama service.</div>',
            unsafe_allow_html=True,
        )
    with runtime:
        st.markdown(
            f'<div class="runtime-card"><div class="runtime-kicker">Local engine</div>'
            f'<div class="runtime-model">{MODEL}</div><div class="runtime-endpoint">127.0.0.1:11434</div>'
            f'{_status_chip("Ollama service", status["ollama"])}'
            f'{_status_chip("Required model", status["model"])}'
            f'{_status_chip("Python dependencies", status["pytest"] and status["ollama_package"])}</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-rule">The execution loop</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="workflow">'
        '<div class="workflow-step"><span class="step-num">01 / INPUT</span><span class="step-name">Read the target module</span></div>'
        '<div class="workflow-step"><span class="step-num">02 / GENERATE</span><span class="step-name">Draft focused pytest cases</span></div>'
        '<div class="workflow-step"><span class="step-num">03 / EXECUTE</span><span class="step-name">Run with a 10s cap</span></div>'
        '<div class="workflow-step"><span class="step-num">04 / REPAIR</span><span class="step-name">Feed failures back locally</span></div>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-rule">Project workspace</div>', unsafe_allow_html=True)
    st.markdown('<div class="workspace-intro">A live view of the input, generated artifact, and current run.</div>', unsafe_allow_html=True)
    try:
        source = TARGET_FILE.read_text(encoding="utf-8")
    except OSError as exc:
        st.error(f"Could not read {TARGET_FILE.name}: {exc}")
        return

    source_col, output_col = st.columns([1, 1], gap="large")
    with source_col:
        st.markdown(
            '<div class="panel-heading"><span class="panel-title">Target module</span>'
            '<span class="panel-tag">target_code.py · input</span></div>',
            unsafe_allow_html=True,
        )
        st.code(source, language="python", line_numbers=True)
        st.markdown(
            '<div class="support-card"><strong>Demo surface</strong><br>'
            'Two small functions with meaningful boundaries: tiered price rounding and username cleanup. '
            'The model sees this exact source when it creates tests.</div>',
            unsafe_allow_html=True,
        )

    with output_col:
        st.markdown(
            '<div class="panel-heading"><span class="panel-title">Generated test file</span>'
            '<span class="panel-tag">test_target.py · output</span></div>',
            unsafe_allow_html=True,
        )
        if GENERATED_FILE.is_file():
            try:
                generated = GENERATED_FILE.read_text(encoding="utf-8")
            except OSError as exc:
                st.error(f"Could not read generated tests: {exc}")
            else:
                st.code(generated, language="python", line_numbers=True)
        else:
            st.info("Generated tests will appear here after the first local run.")
        st.markdown(
            '<div class="support-card"><strong>Repair boundary</strong><br>'
            'The repair loop updates generated tests only. It never rewrites the target module.</div>',
            unsafe_allow_html=True,
        )

    run_col, log_col = st.columns([0.78, 1.22], gap="large", vertical_alignment="top")
    with run_col:
        st.markdown('<div class="panel-title">Start a run</div>', unsafe_allow_html=True)
        st.caption("One generation plus up to three repairs. Each pytest run is capped at 10 seconds.")
        ready = bool(status["ollama"] and status["model"] and status["pytest"] and status["ollama_package"])
        run_clicked = st.button("Generate and run tests", type="primary", disabled=not ready, use_container_width=True)
        if not ready:
            missing = _install_instructions(status)
            st.markdown('<div class="support-card"><strong>Local runtime not ready</strong><br>' +
                        "<br>".join(missing) + "</div>", unsafe_allow_html=True)
        else:
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
            log_placeholder.code("\n".join(saved_logs), language="text")
        else:
            log_placeholder.info("The run trace will show model requests, pytest results, and repair steps.")

        if run_clicked:
            st.session_state["run_logs"] = []

            def show_event(event: dict[str, Any]) -> None:
                entries = list(event.get("logs", []))
                st.session_state["run_logs"] = entries
                log_placeholder.code("\n".join(entries), language="text")

            with st.spinner("Generating and executing locally…"):
                result = TestForgeEngine(model=MODEL).generate_and_heal(
                    source,
                    str(GENERATED_FILE),
                    max_retries=3,
                    on_event=show_event,
                )
            st.session_state["last_result"] = result
            st.session_state["run_logs"] = result.get("logs", [])
            if result["passed"]:
                st.success(f"Verified — pytest passed in {result['iterations']} iteration(s).")
            else:
                st.error(result.get("error") or "The run did not pass.")
                if result.get("stderr"):
                    st.caption(str(result["stderr"]))

    previous = st.session_state.get("last_result")
    if previous:
        with st.expander("Execution details", expanded=False):
            st.write(
                f"Status: {'passed' if previous['passed'] else 'failed'} · "
                f"Iterations: {previous.get('iterations', 0)} · "
                f"Return code: {previous.get('returncode', -1)}"
            )
            if previous.get("stdout"):
                st.code(previous["stdout"], language="text")
            if previous.get("stderr"):
                st.code(previous["stderr"], language="text")

    st.markdown(
        '<div class="footerline">OPEN TEST &nbsp; / &nbsp; PYTEST EXECUTION HARNESS &nbsp; / &nbsp; '
        'SOURCE AND MODEL TRAFFIC STAY LOCAL</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
