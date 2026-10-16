# Build prompt for the Agentic 3D pipeline

You are implementing the 16 Bash components of a source-to-series intelligence pipeline in this repository. The course documents define the contracts. A test harness and the starter's own examples are your acceptance gate. Work in the milestones below, and stop and ask me when something here says to.

## Read first, in this order

1. `README.md`, `ARCHITECTURE.md`, `SUBMISSION.md`, `examples/README.md`
2. `config/project.json`, `config/sources.json`, `config/editorial_policy.md`, `prompts/*.md`
3. `tests/README.md`

`ARCHITECTURE.md` is authoritative. Where this prompt and it disagree, follow `ARCHITECTURE.md` and tell me. Do not change record formats, file paths, exit codes or receipt behavior.

## Decisions already made (do not reopen)

**Platform and structure**
- Runs on macOS: system Bash 3.2 and BSD tools. It must also run on Linux. No Bash 4 features, no GNU-only `date`/`sed`/`stat`, no `timeout`.
- Keep each Bash script thin: arguments, exit codes, and choosing `.venv/bin/python`. Put the real logic in Python helpers named for their component (for example `data/store_db.py`, `processing/filter_items.py`). No single shared module that all scripts call. One small helper for invoking Codex and validating its JSON is allowed, but stage logic stays in each stage.
- Use the Python standard library where you can. Pin other dependencies in `requirements.txt` (faster-whisper, yt-dlp, anything else). `run.sh` uses `.venv/bin/python` and exits 2 with a clear message if the environment is missing.

**Models and cost**
- The only model access is Codex CLI. No API keys, no paid APIs. Never put secrets in the repo.
- Send eligible items to Codex in batches of about 10, with metadata and a bounded excerpt. Give full evidence only to `create_briefs` for accepted items.
- Validate every Codex response as strict JSONL. Retry once. If it is still invalid, fail the stage with exit 1. Write outputs only after they validate, and keep raw responses under `RUN_DIR/logs/`.
- Record the model name Codex reports in receipts, or "default, name not reported". Record cost as `null`. Never guess either.

**Evidence and identity**
- Store: SQLite behind `data/store.sh` only, in the evidence folder under `data/`. Nothing else touches that folder.
- `version_id`: SHA-256 of sorted, compact JSON of title, URL, publication date, extracted text and transcript segments (the examples' method). Retrieval time never creates a new version.
- `item_id`: `feed:`, `youtube:` or `podcast:` plus the native ID (GUID, video ID), else the canonical URL.
- A podcast episode and its YouTube upload are one item. YouTube is primary and the podcast ID is an alias. Match on same `publisher_id`, normalized title, date within 2 days, and similar duration as a tie-breaker. Log every merge in the receipt. Flag uncertain matches instead of merging.
- Keep text and transcript segments under `data/assets/` (paths relative to the repo root). Do not store audio or video in the repo.

**Collection**
- Window: read `freshness_window_days` (currently 30) from the run's config snapshot, never from the live config. Window start is as-of minus (N - 1) days, in UTC. As-of is the actual UTC execution date. Record each item's age in days. `run.sh` warns when a live run uses anything other than 30.
- Collect at most `max_items_per_source` (3) newest items per source, and note in the receipt when the cap cut items off.
- YouTube: discover through channel or playlist Atom feeds. Prefer captions via `yt-dlp`, else transcribe with faster-whisper using `whisper_model` from `project.json` (tiny). Podcasts: download the audio enclosure and transcribe. Cache transcripts so reruns skip them.
- Written items: use full feed content when present, else fetch the page and extract the main text with one pinned approach. If extraction fails (paywall, block), record `extraction_failed` in the receipt and skip the item. Never store partial text as evidence.
- Skip audio longer than 90 minutes and record `skipped_too_long`.
- An unreachable source must make `fetch_*.sh` exit 1 and keep partial results. The workflow continues, and the summary shows incomplete coverage.
- Automatic transcripts can garble numbers and names. Do not "correct" them. The editorial policy handles verification.

## Milestones (run the tests after each; do not edit anything under `tests/`)

1. `data/store.sh`: `bash tests/run_tests.sh store` and `bash tests/run_tests.sh examples`
2. `processing/filter_items.sh`: `bash tests/run_tests.sh filter`
3. `review/check_content.sh`, `publishing/prepare_package.sh`, `reporting/summarize_run.sh`: `check_content`, `package`, `summary`
4. `collectors/*`: test offline with local `file://` fixtures; no network in tests.
5. `processing/extract_content.sh`
6. AI stages: `editorial/select_items.sh`, `editorial/create_briefs.sh`, `content/write_articles.sh`, `content/write_video_scripts.sh`. Use `prompts/*.md` as given.
7. `workflows/collect_sources.sh`, `workflows/create_series.sh`, `run.sh`: `bash tests/run_tests.sh run`
8. Run `bash tests/run_tests.sh` in full, then stop. I will run the live pipeline and then `python3 tests/validate_run.py runs/RUN_ID`.

For every component: the contract in `ARCHITECTURE.md`, exit codes 0, 1 and 2, a uniquely named receipt per invocation with earlier receipts preserved, and no network access in unit tests.

## Rules of engagement

- Do not run live collection or real Codex calls, and do not publish anything, until I say so.
- Do not edit `config/` or `prompts/` except to fix a syntax error, and tell me if you do.
- If a test looks wrong, or two documents conflict, stop and show me. Do not work around either.
- Keep `docs/build_notes.md` with each decision, assumption and deviation, in plain language, so I can reuse it in `SUBMISSION.md`.
- After each milestone, report: what changed, which tests pass or fail, assumptions you made, and anything that needs my decision.
