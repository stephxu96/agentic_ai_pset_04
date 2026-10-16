# Handoff: Agentic 3D (MIT 1.125 Problem Set 4)

For a fresh Claude session working in this folder. Read this file first, then `README.md`, `ARCHITECTURE.md` and `docs/BUILD_PROMPT.md`. Written Oct 15, 2026. The student (Steph) has said the assignment is due Oct 16-17.

## The project

Build an automated pipeline (16 Bash components, defined in `ARCHITECTURE.md`) that collects sources, filters them to a freshness window, has Codex CLI select and synthesize evidence, and produces three connected articles and three videos. The publication is **Agentic 3D**: frontier AI for 3D modeling, CAD, and intelligent systems acting in physical space, with 3D and CAD leading and robotics supporting, plus what AI-native startups are shipping. The audience is technical product managers and engineering leaders deciding where to build on frontier models for spatial and geometric work. The recurring question is in `config/project.json`.

## Your role

You are the TPM and system designer, not the coder. A separate builder (Codex CLI) writes the 16 scripts from `docs/BUILD_PROMPT.md`. The student reviews its work. Do not write the pipeline code unless asked. You may write specs, test harness code, config, prompts and documents.

## How she wants to work

- She decides; you recommend. Ask one focused question at a time, and give a recommendation when she says "not sure."
- Do not stall, drift, or re-raise settled decisions or her timeline. Stay on the task she gave.
- Be direct about limits. Never present an unverified URL, feed or claim as confirmed, and say plainly when you cannot do something (for example access her machine).
- Do not ask her for details that belong to the builder's implementation.

## Decisions made (do not reopen)

- **Platform:** macOS, Bash 3.2 and BSD tools, also Linux-safe. Bash scripts are thin; logic lives in Python helpers named for their component. Dependencies in `requirements.txt` with a `.venv`.
- **Model:** Codex CLI only, no APIs. Batches of about 10 items, strict JSONL validation, retry once, then fail the stage (exit 1). Cost recorded as null; model name recorded as Codex reports it.
- **Store:** SQLite behind `data/store.sh` only. `item_id` is `feed:`, `youtube:` or `podcast:` plus the native ID or canonical URL. A podcast and its YouTube upload are one item, YouTube primary.
- **Window:** `freshness_window_days` is 45 in `config/project.json`, read from the run's config snapshot. The README standard is 30. The student says course staff approved 45, and the written approval still needs to be saved in the repo. Collect at most 3 newest items per source.
- **Transcripts:** YouTube captions first, else faster-whisper with the `tiny` model. Skip audio over 90 minutes. Keep text and segments in `data/assets/`, never media.
- **Publishing:** videos built as PowerPoint slide decks (one slide per scene) with a Chatterbox voiceover cloned from the author's voice, combined with ffmpeg; no avatar. YouTube videos public. Technical demo video on Google Drive. Substack and YouTube accounts: she decides after the first live run (the README requires published links). `publication_links.json` stays null until then.
- **Evidence for grading:** second run uses a new run with a revised policy. A labeled `replay` run withholds one eligible item, then adds it. The simulated failure is an unreachable feed URL (a `.invalid` address), labeled as simulated. Editorial review is written in `docs/editorial_review.md`.
- **Assumptions I chose, which she can change:** extraction failures are skipped and logged (`extraction_failed`); the 90-minute audio cap; the episode-matching rule in `BUILD_PROMPT.md`.

## Status

- **Done by the previous session:** config, prompts and editorial policy; a 141-test harness in `tests/` (`bash tests/run_tests.sh`, and `python3 tests/validate_run.py runs/RUN_ID` after real runs); `tools/find_feeds.py`; `docs/BUILD_PROMPT.md`; the starter's own `examples/` checks added as tests.
- **Builder:** was blocked first by missing files, then reported that `sources.json` lacked written and YouTube sources. It has implemented essentially nothing yet. The 16 scripts should be treated as not built until tests show otherwise.
- **`config/sources.json`:** 15 sources, but only two feeds are verified (Researcher's Guide, Lex Fridman). The rest carry "UNVERIFIED guess" notes. The student must run `python3 tools/find_feeds.py tools/candidate_sites.txt --emit sources_draft.json` on her machine, then merge the verified entries before any live run. Physical Intelligence's blog and the MIT CDFG survey are excluded (no feed).

## Open items

1. Run the feed finder and finalize `sources.json`.
2. Builder milestones 1-8, checked against the tests.
3. First live run, review, policy revision, second live run on a different day, replay run.
4. Pick the item to withhold for the replay.
5. Substack and YouTube decision.
6. Write `SUBMISSION.md` (mostly empty) and `docs/editorial_review.md`, and save the staff approval for the 45-day window.
7. Slide-deck videos with the Chatterbox voiceover, and the technical demo.

## Risks

- Deadline pressure: priorities by grade weight are architecture and repeatability, then evidence and editorial, then communication.
- Live runs use Codex CLI usage that may be limited.
- Automatic transcripts from the tiny model can garble numbers and names, so claims must be checked against audio.
- Items 31-44 days old will enter under the 45-day window. Keep the 12-item, 6-publisher, 2-per-kind minimums achievable with items within 30 days where possible.

## File map

`config/` project, sources, policy. `prompts/` four stage prompts. `tests/` harness and validator. `tools/` feed finder. `docs/` build prompt, editorial review template, freshness-window section draft, this handoff. `examples/` the starter's own format examples (never use as evidence).
