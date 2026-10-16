#!/usr/bin/env bash
# Usage: bash tests/run_tests.sh [component-pattern]
# Examples: bash tests/run_tests.sh | bash tests/run_tests.sh store | bash tests/run_tests.sh filter
cd "$(dirname "$0")/.." || exit 2
if [ -n "$1" ]; then
  python3 -m unittest discover -s tests -p "test_*${1}*.py" -v
else
  python3 -m unittest discover -s tests -p 'test_*.py' -v
fi
