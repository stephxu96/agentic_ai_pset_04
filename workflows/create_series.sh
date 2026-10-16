#!/usr/bin/env bash
# Coordinate editorial selection, three briefs, both formats, and content review.
set -u

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)" || exit 2
if [ "$#" -ne 1 ]; then echo "usage: workflows/create_series.sh RUN_DIR" >&2; exit 2; fi
RUN_DIR="$1"
case "$RUN_DIR" in /*|*..*) echo "RUN_DIR must be repository-relative" >&2; exit 2 ;; esac
RUN_PATH="$ROOT_DIR/$RUN_DIR"
if [ ! -d "$RUN_PATH" ]; then echo "run directory does not exist: $RUN_DIR" >&2; exit 2; fi

overall=0
if bash "$ROOT_DIR/editorial/select_items.sh" "$RUN_DIR" < "$RUN_PATH/eligible.jsonl" > "$RUN_PATH/decisions.jsonl"; then
  :
else
  status=$?
  echo "create_series: item selection exited $status" >&2
  exit 1
fi

if bash "$ROOT_DIR/editorial/create_briefs.sh" "$RUN_DIR" < "$RUN_PATH/decisions.jsonl" > "$RUN_PATH/briefs.jsonl"; then
  :
else
  status=$?
  echo "create_series: brief creation exited $status" >&2
  exit 1
fi

if bash "$ROOT_DIR/content/write_articles.sh" "$RUN_DIR" < "$RUN_PATH/briefs.jsonl" > "$RUN_PATH/articles.jsonl"; then
  :
else
  status=$?
  echo "create_series: article generation exited $status" >&2
  overall=1
fi
if bash "$ROOT_DIR/content/write_video_scripts.sh" "$RUN_DIR" < "$RUN_PATH/briefs.jsonl" > "$RUN_PATH/video_scripts.jsonl"; then
  :
else
  status=$?
  echo "create_series: video script generation exited $status" >&2
  overall=1
fi

if bash "$ROOT_DIR/review/check_content.sh" "$RUN_DIR" > /dev/null; then
  :
else
  status=$?
  echo "create_series: content assessment could not run (exit $status)" >&2
  overall=1
fi
exit "$overall"
