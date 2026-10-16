#!/usr/bin/env bash
# Verify approval and assemble the reviewed production handoff package.
set -u

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)" || exit 2
PYTHON="$ROOT_DIR/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then PYTHON="$(command -v python3 2>/dev/null || true)"; fi
if [ -z "$PYTHON" ]; then echo "publishing/prepare_package.sh: Python 3 is required" >&2; exit 2; fi
exec "$PYTHON" "$ROOT_DIR/publishing/prepare_package.py" "$@"
