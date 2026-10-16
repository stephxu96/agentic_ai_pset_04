#!/usr/bin/env python3
"""Validate configuration and orchestrate full and package-only pipeline runs."""

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPT_NAMES = ("select_items.md", "create_briefs.md", "write_articles.md", "write_video_scripts.md")


class UsageError(Exception):
    pass


def utc_now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_run_path(value):
    if not isinstance(value, str) or not value or os.path.isabs(value):
        raise UsageError("RUN_DIR must be a repository-relative path")
    path = (ROOT / value).resolve()
    if path != ROOT and ROOT not in path.parents:
        raise UsageError("RUN_DIR must stay within the repository")
    return path


def read_json(path, label):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise UsageError("missing %s: %s" % (label, path.relative_to(ROOT)))
    except (OSError, json.JSONDecodeError) as exc:
        raise UsageError("cannot read %s: %s" % (label, exc))


def validate_config():
    project = read_json(ROOT / "config" / "project.json", "config/project.json")
    if not isinstance(project, dict):
        raise UsageError("config/project.json must contain a JSON object")
    for key in ("publication_name", "topic", "audience", "central_question"):
        if not isinstance(project.get(key), str) or not project[key].strip():
            raise UsageError("project.json %s must be a nonempty string" % key)
    window = project.get("freshness_window_days", 30)
    if isinstance(window, bool) or not isinstance(window, int) or window <= 0:
        raise UsageError("project.json freshness_window_days must be a positive integer")
    cap = project.get("max_items_per_source", 3)
    if isinstance(cap, bool) or not isinstance(cap, int) or cap <= 0:
        raise UsageError("project.json max_items_per_source must be a positive integer")
    sources = read_json(ROOT / "config" / "sources.json", "config/sources.json")
    if not isinstance(sources, list):
        raise UsageError("config/sources.json must be a JSON array")
    for i, source in enumerate(sources):
        if not isinstance(source, dict):
            raise UsageError("source %d must be an object" % i)
        for key in ("source_id", "publisher_id", "url"):
            if not isinstance(source.get(key), str) or not source[key].strip():
                raise UsageError("source %d requires nonempty %s" % (i, key))
        if source.get("kind") not in ("feed", "youtube", "podcast"):
            raise UsageError("source %d kind must be feed, youtube or podcast" % i)
    policy = ROOT / "config" / "editorial_policy.md"
    if not policy.is_file():
        raise UsageError("missing config/editorial_policy.md")
    for name in PROMPT_NAMES:
        prompt = ROOT / "prompts" / name
        if not prompt.is_file() or not prompt.read_text(encoding="utf-8").strip():
            raise UsageError("missing or empty prompts/%s" % name)
    return project


def record_receipt(run_path, stage, status, error=None):
    logs = run_path / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    name = "%s-%s.json" % (stage.replace("/", "-").replace(".", "-"), uuid.uuid4().hex)
    value = {"stage": stage, "status": status, "input_count": None, "output_count": None,
             "started_at": utc_now(), "finished_at": utc_now(), "tools": ["bash workflows"],
             "cost_usd": None}
    if error:
        value["errors"] = [error]
    with (logs / name).open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True)
        handle.write("\n")


def run_command(args, stdout_path=None, cwd=None, stdin_path=None):
    stdin_handle = None
    try:
        if stdin_path:
            stdin_handle = open(str(stdin_path), "r", encoding="utf-8")
        proc = subprocess.run(args, cwd=str(cwd or ROOT), text=True,
                              stdin=stdin_handle,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, check=False)
    except OSError as exc:
        return 127, str(exc)
    finally:
        if stdin_handle:
            stdin_handle.close()
    if stdout_path:
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_path.write_text(proc.stdout or "", encoding="utf-8")
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    return proc.returncode, "" if proc.returncode == 0 else "command exited %d" % proc.returncode


def save_summary(run_dir):
    summary_path = run_dir / "summary.json"
    code, error = run_command(["bash", str(ROOT / "reporting" / "summarize_run.sh"),
                               run_dir.relative_to(ROOT).as_posix()])
    if code != 0:
        return code, error, None
    try:
        result = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return 1, "summary output is invalid: %s" % exc, None
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return 0, "", result


def package_mode(run_value):
    run_path = safe_run_path(run_value)
    if not run_path.is_dir() or not (run_path / "run.json").is_file():
        raise UsageError("--package requires an existing run directory containing run.json")
    run_rel = run_path.relative_to(ROOT).as_posix()
    review_code, review_error = run_command(
        ["bash", str(ROOT / "review" / "check_content.sh"), run_rel],
        stdout_path=run_path / "review.json")
    package_code, package_error = run_command(
        ["bash", str(ROOT / "publishing" / "prepare_package.sh"), run_rel],
        stdout_path=None)
    summary_code, summary_error, _ = save_summary(run_path)
    if review_code or package_code or summary_code:
        details = "; ".join(x for x in (review_error, package_error, summary_error) if x)
        if details:
            print("run.sh --package: " + details, file=sys.stderr)
        return 1
    return 0


def previous_run_id():
    runs = ROOT / "runs"
    candidates = []
    if runs.is_dir():
        for folder in runs.iterdir():
            if not folder.is_dir():
                continue
            try:
                meta = json.loads((folder / "run.json").read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(meta, dict) and isinstance(meta.get("started_at"), str):
                candidates.append((meta["started_at"], meta.get("run_id", folder.name)))
    return max(candidates)[1] if candidates else None


def create_run(project, as_of=None, mode="live", extra=None, include_backup=False):
    now = dt.datetime.now(dt.timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%S") + ("%06dZ" % now.microsecond)
    run_id = stamp
    run_path = ROOT / "runs" / run_id
    while run_path.exists():
        run_id += "-" + uuid.uuid4().hex[:6]
        run_path = ROOT / "runs" / run_id
    (run_path / "logs").mkdir(parents=True)
    (run_path / "config").mkdir()
    (run_path / "prompts").mkdir()
    for name in ("project.json", "editorial_policy.md"):
        shutil.copy2(ROOT / "config" / name, run_path / "config" / name)
    # Sources marked "tier": "backup" run only with --with-backup (and in replays, which read the store).
    all_sources = json.loads((ROOT / "config" / "sources.json").read_text(encoding="utf-8"))
    active = [x for x in all_sources if include_backup or x.get("tier") != "backup"]
    (run_path / "config" / "sources.json").write_text(
        json.dumps(active, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name in PROMPT_NAMES:
        shutil.copy2(ROOT / "prompts" / name, run_path / "prompts" / name)
    checks = ROOT / "config" / "selection_checks.jsonl"
    if checks.is_file():
        shutil.copy2(checks, run_path / "selection_checks.jsonl")
    started = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    meta = {"run_id": run_id, "started_at": started,
            "as_of_date": as_of.isoformat() if as_of else now.date().isoformat(),
            "mode": mode, "previous_run_id": previous_run_id()}
    if extra:
        meta.update(extra)
    (run_path / "run.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return run_id, run_path


def live_mode(project, include_backup=False):
    window = project.get("freshness_window_days", 30)
    if window != 30:
        print("run.sh: warning: configured freshness window is %d days (assignment default is 30); "
              "using the documented project window." % window, file=sys.stderr)
    run_id, run_path = create_run(project, include_backup=include_backup,
                                  extra={"include_backup": include_backup})
    run_rel = run_path.relative_to(ROOT).as_posix()
    failures = []
    init_code, init_error = run_command(["bash", str(ROOT / "data" / "store.sh"), "init"])
    if init_code:
        failures.append("evidence store initialization: " + init_error)
    collect_code, collect_error = run_command(
        ["bash", str(ROOT / "workflows" / "collect_sources.sh"), run_rel])
    record_receipt(run_path, "workflows/collect_sources.sh",
                   "failed" if collect_code else "completed", collect_error or None)
    if collect_code:
        failures.append("collection workflow: " + collect_error)
    # Even incomplete collection may have yielded enough usable evidence to review.
    series_code, series_error = run_command(
        ["bash", str(ROOT / "workflows" / "create_series.sh"), run_rel])
    record_receipt(run_path, "workflows/create_series.sh",
                   "failed" if series_code else "completed", series_error or None)
    if series_code:
        failures.append("series workflow: " + series_error)
    summary_code, summary_error, _ = save_summary(run_path)
    if summary_code:
        failures.append("summary: " + summary_error)
    if failures:
        for message in failures:
            print("run.sh: " + message, file=sys.stderr)
        return 1
    return 0


REPLAY_THROUGH = ("eligible", "selection", "briefs")
REPLAY_NOTE = ("Replay: reads items already in the evidence store and applies the freshness window as of "
               "as_of_date. Nothing was collected on that date. Items published after as_of_date are excluded "
               "as future_date. The store holds the latest saved version of each item, and the per-source "
               "item cap is not applied. This is a labeled simulation, not a live run.")


def replay_mode(project, as_of, through):
    today = dt.datetime.now(dt.timezone.utc).date()
    if as_of > today:
        raise UsageError("--as-of must not be in the future")
    extra = {"replay_note": REPLAY_NOTE, "replay_through": through,
             "executed_at": utc_now()}
    run_id, run_path = create_run(project, as_of=as_of, mode="replay", extra=extra, include_backup=True)
    run_rel = run_path.relative_to(ROOT).as_posix()
    print("run.sh: replay run %s, as-of %s, through %s (labeled replay; no collection)"
          % (run_id, as_of.isoformat(), through), file=sys.stderr)
    failures = []

    def step(label, args, stdin_name=None, stdout_name=None):
        code, error = run_command(
            args, stdout_path=(run_path / stdout_name) if stdout_name else None,
            stdin_path=(run_path / stdin_name) if stdin_name else None)
        if code:
            failures.append("%s: %s" % (label, error))
        return code

    init_code, init_error = run_command(["bash", str(ROOT / "data" / "store.sh"), "init"])
    if init_code:
        failures.append("evidence store initialization: " + init_error)
    elif step("store list", ["bash", str(ROOT / "data" / "store.sh"), "list"], stdout_name="corpus.jsonl") == 0:
        if step("freshness filter", ["bash", str(ROOT / "processing" / "filter_items.sh"), run_rel],
                stdin_name="corpus.jsonl", stdout_name="eligible.jsonl") == 0 and through in ("selection", "briefs"):
            if step("item selection", ["bash", str(ROOT / "editorial" / "select_items.sh"), run_rel],
                    stdin_name="eligible.jsonl", stdout_name="decisions.jsonl") == 0 and through == "briefs":
                step("brief creation", ["bash", str(ROOT / "editorial" / "create_briefs.sh"), run_rel],
                     stdin_name="decisions.jsonl", stdout_name="briefs.jsonl")
    record_receipt(run_path, "run.sh --replay", "failed" if failures else "completed",
                   "; ".join(failures) or None)
    summary_code, summary_error, _ = save_summary(run_path)
    if summary_code:
        failures.append("summary: " + summary_error)
    for message in failures:
        print("run.sh: " + message, file=sys.stderr)
    return 1 if failures else 0


def parse_replay(argv):
    as_of = None
    through = "eligible"
    rest = list(argv)
    i = 1
    while i < len(rest):
        arg = rest[i]
        if arg == "--as-of" and i + 1 < len(rest):
            try:
                as_of = dt.date.fromisoformat(rest[i + 1])
            except ValueError:
                raise UsageError("--as-of must be a valid YYYY-MM-DD date")
            i += 2
        elif arg == "--through" and i + 1 < len(rest):
            through = rest[i + 1]
            if through not in REPLAY_THROUGH:
                raise UsageError("--through must be one of: " + ", ".join(REPLAY_THROUGH))
            i += 2
        else:
            raise UsageError("usage: run.sh --replay --as-of YYYY-MM-DD [--through eligible|selection|briefs]")
    if as_of is None:
        raise UsageError("--replay requires --as-of YYYY-MM-DD")
    return as_of, through


def main(argv):
    if argv and argv[0] == "--replay":
        as_of, through = parse_replay(argv)
        return replay_mode(validate_config(), as_of, through)
    if argv and argv[0] == "--package":
        if len(argv) != 2:
            raise UsageError("usage: run.sh --package RUN_DIR")
        # Validate current project configuration before stage or tool checks.
        validate_config()
        return package_mode(argv[1])
    if argv == ["--with-backup"]:
        return live_mode(validate_config(), include_backup=True)
    if argv:
        raise UsageError("usage: run.sh [--with-backup | --package RUN_DIR | --replay --as-of YYYY-MM-DD [--through eligible|selection|briefs]]")
    project = validate_config()
    return live_mode(project)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except UsageError as exc:
        print("run.sh: %s" % exc, file=sys.stderr)
        sys.exit(2)
