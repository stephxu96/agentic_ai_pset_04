#!/usr/bin/env bash
# Summarize the saved artifacts and receipts for a complete or partial run.
set -u

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)" || exit 2
PYTHON="$ROOT_DIR/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then PYTHON="$(command -v python3 2>/dev/null || true)"; fi
if [ -z "$PYTHON" ]; then echo "reporting/summarize_run.sh: Python 3 is required" >&2; exit 2; fi
exec "$PYTHON" "$ROOT_DIR/reporting/summarize_run.py" "$@"
