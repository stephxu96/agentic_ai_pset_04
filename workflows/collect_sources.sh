#!/usr/bin/env bash
# Collect candidates, retain evidence, and filter the current corpus.
set -u

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)" || exit 2
if [ "$#" -ne 1 ]; then
  echo "usage: workflows/collect_sources.sh RUN_DIR" >&2
  exit 2
fi
RUN_DIR="$1"
case "$RUN_DIR" in /*|*..*) echo "RUN_DIR must be repository-relative" >&2; exit 2 ;; esac
RUN_PATH="$ROOT_DIR/$RUN_DIR"
if [ ! -d "$RUN_PATH" ]; then echo "run directory does not exist: $RUN_DIR" >&2; exit 2; fi
mkdir -p "$RUN_PATH/candidates" "$RUN_PATH/logs" || exit 1

overall=0
for kind in feeds youtube podcasts; do
  case "$kind" in
    feeds) script="$ROOT_DIR/collectors/fetch_feeds.sh" ;;
    youtube) script="$ROOT_DIR/collectors/fetch_youtube.sh" ;;
    podcasts) script="$ROOT_DIR/collectors/fetch_podcasts.sh" ;;
  esac
  if bash "$script" "$RUN_DIR" > "$RUN_PATH/candidates/$kind.jsonl"; then
    :
  else
    status=$?
    overall=1
    echo "collect_sources: $kind collector exited $status; retaining partial results" >&2
  fi
done

cat "$RUN_PATH/candidates/feeds.jsonl" "$RUN_PATH/candidates/youtube.jsonl" \
  "$RUN_PATH/candidates/podcasts.jsonl" > "$RUN_PATH/candidates.jsonl" || exit 1

if bash "$ROOT_DIR/processing/extract_content.sh" "$RUN_DIR" < "$RUN_PATH/candidates.jsonl" > "$RUN_PATH/items.jsonl"; then
  :
else
  status=$?
  overall=1
  echo "collect_sources: extraction exited $status; retaining usable items" >&2
fi

if bash "$ROOT_DIR/data/store.sh" upsert "$RUN_DIR" < "$RUN_PATH/items.jsonl" > "$RUN_PATH/changes.jsonl"; then
  :
else
  echo "collect_sources: evidence-store update failed" >&2
  overall=1
fi

if bash "$ROOT_DIR/data/store.sh" list > "$RUN_PATH/corpus.jsonl"; then
  :
else
  echo "collect_sources: evidence-store export failed" >&2
  overall=1
  : > "$RUN_PATH/corpus.jsonl"
fi

if bash "$ROOT_DIR/processing/filter_items.sh" "$RUN_DIR" < "$RUN_PATH/corpus.jsonl" > "$RUN_PATH/eligible.jsonl"; then
  :
else
  status=$?
  echo "collect_sources: date filtering exited $status" >&2
  overall=1
fi
exit "$overall"
