# Test harness for the PS4 intelligence pipeline

Checks your Bash components against the contracts in `ARCHITECTURE.md`. It needs only
`python3` (standard library; no `jq`, `sqlite3`, or `pip install`). It never touches your real
`data/evidence/`, `data/assets/`, or `runs/`: every test runs in a throwaway copy of the repo.

## Run it

From the repo root:

```bash
bash tests/run_tests.sh              # everything
bash tests/run_tests.sh store        # only test_*store*.py
bash tests/run_tests.sh filter
python3 -m unittest discover -s tests -p 'test_10_store.py' -v   # one file, verbose
```

A component that is still an empty file fails with `... is not implemented yet`, so you work
from red to green. Suggested order: `store`, `filter`, `check_content`, `package`, `summary`, `run`.

After any real run, validate its artifacts:

```bash
python3 tests/validate_run.py runs/RUN_ID
python3 tests/validate_run.py runs/RUN_ID --no-store   # skip calling data/store.sh
```

It exits 1 on any ERROR. WARN lines need your judgment. It checks record shapes, that every
eligible item has exactly one decision, that quotes appear verbatim in the stored text, that
segment IDs exist, at least three independent publishers per piece, all three input types
across the series, items inside the window (and a warning for items 30-44 days old), claim
markers in drafts, article/script consistency, approval/review matching, and the README minimums
(12 items, 6 publishers, 2 per kind).

## What is covered

| File | Component | Highlights |
| --- | --- | --- |
| `test_00_static.py` | repo and config | 16 scripts exist, implemented, Bash shebang, `bash -n`; config shapes; only `store.sh` touches `data/evidence`; no committed credentials |
| `test_05_examples.py` | the starter's `examples/` | the course's own four deterministic checks (store ingest and replay, date filter, brief references), run against your `store.sh` and `filter_items.sh`, plus a check that the harness's record contracts accept the starter's example files |
| `test_10_store.py` | `data/store.sh` | init idempotent; new/changed/unchanged in input order; duplicate in one ingestion; retrieval time alone is not a version; history; list/get; exit codes; receipts |
| `test_20_filter.py` | `filter_items.sh` | inclusive window (as-of minus 29 through as-of); uses the run's as-of date; `unknown_date`, `invalid_date`, `future_date`, `outside_window`; **`freshness_window_days` read from the run snapshot (45 days tested)** |
| `test_30_check_content.py` | `check_content.sh` | exits 0 even when `passed` is false; blocking errors; `review_id` changes with drafts, scripts, briefs, evidence, as-of date |
| `test_40_package.py` | `prepare_package.sh` | refuses without, stale, or mismatched approval and when drafts change after approval; manifest; links start `null` and survive repackaging |
| `test_50_summary.py` | `summarize_run.sh` | works on incomplete runs; `null` vs `0`; counts; status values; costs not claimed as zero |
| `test_60_run.py` | `run.sh` | config validation exits 2; `--package` does not recollect or regenerate |
| `test_feed_finder.py` | `tools/find_feeds.py` | feed discovery, window counting, podcast detection and YouTube ID parsing, all offline |

## What it cannot test

Collectors, `extract_content.sh`, the four AI stages (`select_items`, `create_briefs`, the two
writers) and the two workflows need the network or Codex CLI, so they are not unit tested.
Cover them by running `bash run.sh` and then `validate_run.py`: it checks everything those
stages produce. To test them offline, point `config/sources.json` at local fixture files and
put a fake `codex` script on your `PATH` that prints canned JSON.

## Assumptions (change the harness if your design differs)

- Components run as `bash path RUN_DIR` from the repo root, with JSONL on stdin where the spec says so.
- The window length is the key `freshness_window_days` in `config/project.json`, read from the
  run's **snapshot** (`RUN_DIR/config/project.json`). Tests set it explicitly.
- `run.sh` validates configuration before any tool or network check, so bad config exits 2.
- `check_content.sh` uses the key `severity` (`error` or `warning`) and some key naming the piece
  or artifact and some key with the explanation. It may read evidence through `eligible.jsonl`
  and `data/store.sh`; the fixtures provide both.
- `prepare_package.sh` may read `review.json` or recompute the check; fixtures provide `review.json`.
- Receipts are matched by concept (stage, status, input/output counts, start/finish, tools or
  models, cost) in any key naming, at any depth.
- Item IDs follow the starter's convention `<kind>:<name>` (`feed:`, `youtube:`, `podcast:`), and file paths are relative to the repo root.
- Fixture assets live under `data/assets/`, which the spec allows for retained text and transcripts.

## How the harness itself was checked

It was run against throwaway stub implementations of six components (all tests passed), then
against ten deliberately injected bugs (off-by-one window, ignoring the configured window, stale
approvals accepted, a review fingerprint that ignores the as-of date, and so on). All ten were
caught by the tests meant to catch them. The stubs are not included.
