#!/usr/bin/env bash
set -u
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)" || exit 2
PYTHON="$ROOT_DIR/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then PYTHON="$(command -v python3 2>/dev/null || true)"; fi
if [ -z "$PYTHON" ]; then echo "editorial/select_items.sh: Python 3 is required" >&2; exit 2; fi
exec "$PYTHON" "$ROOT_DIR/editorial/select_items.py" "$@"
