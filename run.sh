#!/usr/bin/env bash
# Top-level run entry point. Orchestration details live in workflows/run_pipeline.py.
set -u

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)" || exit 2
PYTHON="$ROOT_DIR/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  PYTHON="$(command -v python3 2>/dev/null || true)"
fi
if [ -z "$PYTHON" ]; then
  echo "run.sh: Python 3 is required (activate .venv or install system python3)" >&2
  exit 2
fi
exec "$PYTHON" "$ROOT_DIR/workflows/run_pipeline.py" "$@"
