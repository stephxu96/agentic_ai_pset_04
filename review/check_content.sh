#!/usr/bin/env bash
# Review saved drafts and evidence links; assessment logic lives in check_content.py.
set -u

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)" || exit 2
PYTHON="$ROOT_DIR/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then PYTHON="$(command -v python3 2>/dev/null || true)"; fi
if [ -z "$PYTHON" ]; then echo "review/check_content.sh: Python 3 is required" >&2; exit 2; fi
exec "$PYTHON" "$ROOT_DIR/review/check_content.py" "$@"
