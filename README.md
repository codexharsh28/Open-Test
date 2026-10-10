# Open Test

Open Test generates pytest tests for a Python module with the local
`qwen2.5-coder:3b` Ollama model, runs them in a timeout-bounded subprocess, and
feeds pytest failures back to the model for test repair. It does not call an
external model API.

## Requirements

- macOS on Apple Silicon, Python 3.10 or newer
- [Ollama](https://ollama.com/) installed and running locally
- The model pulled locally: `ollama pull qwen2.5-coder:3b`

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
ollama pull qwen2.5-coder:3b
```

Ollama uses Metal acceleration on supported Apple Silicon systems. The harness
connects to the local Ollama service at `http://127.0.0.1:11434` by default.
Set `OLLAMA_HOST` to a different local Ollama endpoint if needed.

## Run

Generate tests and allow three model repair attempts after the first run:

```bash
python -m harness.generator --target target_code.py
```

Choose a generated test path and retry count with `--test-file` and
`--max-retries`. Each pytest execution has a 10-second timeout.

Launch the three-column dashboard:

```bash
streamlit run app.py
```

The generated test file is written to `test_target.py` in the current working
directory (or to the path supplied with `--test-file`). A repair attempt fixes
the generated tests; it does not edit the target module.

## Demo behavior

`target_code.py` demonstrates `calculate_discount` and `clean_username`.
Discounts return the final price and use standard (0%), silver (10%), and gold
(20%) tiers. Usernames are trimmed and reduced to Unicode alphanumeric
characters; `None` produces an empty string.

## License

MIT. See [LICENSE](LICENSE).
