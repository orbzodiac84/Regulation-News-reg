"""Tests for env-driven Gemini model ID configuration in `src.config.settings`.

The model ID constants in `src.config.settings` are read from the environment
at import time. To test both default and overridden behavior reliably without
polluting other tests' module state, each scenario runs in a fresh subprocess.
"""

import subprocess
import sys


def _run(env_assignments: str, assertions: str) -> None:
    code = (
        "import os\n"
        f"{env_assignments}\n"
        "from src.config.settings import (\n"
        "    MODEL_FILTER_ID, MODEL_ANALYZER_ID, MODEL_ANALYZER_FALLBACK\n"
        ")\n"
        f"{assertions}\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"subprocess failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )


def test_model_ids_default_when_env_unset():
    _run(
        env_assignments=(
            "for k in ('GEMINI_FILTER_MODEL','GEMINI_ANALYZER_MODEL',"
            "'GEMINI_ANALYZER_FALLBACK_MODEL'):\n"
            "    os.environ.pop(k, None)"
        ),
        assertions=(
            "assert MODEL_FILTER_ID == 'gemini-2.5-flash-lite'\n"
            "assert MODEL_ANALYZER_ID == 'gemini-3-flash-preview'\n"
            "assert MODEL_ANALYZER_FALLBACK == 'gemini-1.5-pro'"
        ),
    )


def test_model_ids_overridden_by_env():
    _run(
        env_assignments=(
            "os.environ['GEMINI_FILTER_MODEL'] = 'filter-test'\n"
            "os.environ['GEMINI_ANALYZER_MODEL'] = 'analyzer-test'\n"
            "os.environ['GEMINI_ANALYZER_FALLBACK_MODEL'] = 'fallback-test'"
        ),
        assertions=(
            "assert MODEL_FILTER_ID == 'filter-test'\n"
            "assert MODEL_ANALYZER_ID == 'analyzer-test'\n"
            "assert MODEL_ANALYZER_FALLBACK == 'fallback-test'"
        ),
    )
