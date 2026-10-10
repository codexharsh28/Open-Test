# Product Requirements Document (PRD): Open Test

**Project Name:** Open Test  
**Goal:** Build an autonomous, offline unit-test and self-healing execution harness powered by a local open-weight model (`qwen2.5-coder:3b` via Ollama).  
**Build Time:** Under 2 hours  
**Platform:** macOS (Apple Silicon M2), Python 3.10+  
**License:** MIT  

---

## 1. Core Concept (What It Does)

Open Test takes a target Python file, uses a local LLM to write `pytest` unit tests, runs them in an isolated subprocess, catches any failures/tracebacks, and feeds those errors back to the model in an automated loop until all tests pass 100%.

```
[target_code.py] ──> [Ollama (qwen2.5-coder:3b)] ──> [Run pytest]
                             ▲                              │
                             │                              ▼
                             └─── [Feed Error Traceback] ◄── Fail?
                                                            │ Pass
                                                            ▼
                                                    [Verified Tests]
```

---

## 2. Tech Stack & Dependencies

* **Local LLM:** Ollama running `qwen2.5-coder:3b`
* **Language:** Python 3.10+
* **Core Libraries (`requirements.txt`):**
  * `ollama` (Local model client)
  * `pytest` (Test execution)
  * `pytest-cov` (Coverage reporting)
  * `streamlit` (Demo UI)

---

## 3. Project File Tree

```text
open-test/
├── LICENSE                 # MIT License
├── README.md               # Quickstart & commands
├── SKILL.md                # Agent Skill definition for AI editors
├── requirements.txt        # Python package dependencies
├── target_code.py          # Demo code with edge cases to test
├── harness/
│   ├── __init__.py
│   ├── runner.py           # Subprocess wrapper for pytest
│   └── generator.py        # Ollama caller + self-healing loop
└── app.py                  # Streamlit dashboard
```

---

## 4. Component Specifications

### 4.1 `target_code.py`
A simple Python file containing 2 functions with boundary conditions:
1. `calculate_discount(price: float, tier: str) -> float`: Disallow negative numbers, handle float rounding, check invalid tiers.
2. `clean_username(name: str) -> str`: Strip whitespace, remove special symbols, handle `None` inputs.

### 4.2 `harness/runner.py`
Executes `pytest` safely in a subprocess.
* **Function:** `run_test(test_file: str, timeout: int = 10) -> dict`
* **Behavior:**
  * Runs `pytest <test_file> --maxfail=1 -v` via `subprocess.run()`.
  * Enforces a 10-second timeout to prevent infinite loops.
* **Returns:**
  ```python
  {
      "passed": bool,       # True if returncode == 0
      "stdout": str,       # Captured pytest output
      "stderr": str,
      "returncode": int
  }
  ```

### 4.3 `harness/generator.py`
Connects to Ollama and executes the self-healing loop.
* **Class:** `TestForgeEngine(model="qwen2.5-coder:3b")`
* **Method:** `generate_and_heal(source_code: str, test_file: str = "test_target.py", max_retries: int = 3) -> dict`
* **Loop Logic:**
  1. **Prompt:** Ask the model to generate pure `pytest` code testing `target_code.py`.
  2. **Sanitize:** Strip markdown fences (```` ```python ```` and ```` ``` ````).
  3. **Write:** Save code to `test_target.py`.
  4. **Run:** Call `runner.run_test(test_file)`.
  5. **Check:**
     * If `passed == True`: Return success and logs.
     * If `passed == False`: Append the raw pytest error output to the message history, ask the model to fix the tests, and repeat (up to `max_retries`).

### 4.4 `app.py` (Streamlit Dashboard)
A simple 3-column UI for hackathon presentation:
* **Left:** Text box displaying `target_code.py` + "Run Open Test" button.
* **Middle:** Real-time log showing iterations:
  * Iteration 1: ❌ `AssertionError` detected.
  * Iteration 2: 🔁 Error fed back to local model.
  * Iteration 2: ✅ 4 tests passed.
* **Right:** Syntax-highlighted view of the generated `test_target.py`.

### 4.5 `SKILL.md`
Standard agent tool specification:
```markdown
# Skill: open-test
## Description
Generates and self-heals unit tests locally using open-weight models via an execution harness.
## Command
python -m harness.generator --target target_code.py
```

---

## 5. Build Steps for the AI Coding Agent

1. **Step 1:** Create `requirements.txt`, `LICENSE` (MIT), and `target_code.py`.
2. **Step 2:** Write `harness/runner.py` (subprocess test runner).
3. **Step 3:** Write `harness/generator.py` (Ollama integration and loop).
4. **Step 4:** Write `app.py` (Streamlit interface).
5. **Step 5:** Write `SKILL.md` and `README.md`.

---

## 6. Verification Checklist

* [ ] Ollama is running locally: `ollama run qwen2.5-coder:3b "hello"` returns a response.
* [ ] Running `python -m harness.generator` produces a passing `test_target.py`.
* [ ] At least one failing test is automatically repaired during the loop.
* [ ] `streamlit run app.py` launches cleanly on `http://localhost:8501`.