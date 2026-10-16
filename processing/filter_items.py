#!/usr/bin/env python3
"""Apply a run's snapshotted publication-date window to item JSONL."""

import datetime as dt
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class InputError(Exception):
    pass


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_path(rel, label):
    if not rel or os.path.isabs(rel):
        raise InputError("%s must be a repository-relative path" % label)
    path = (ROOT / rel).resolve()
    if path != ROOT and ROOT not in path.parents:
        raise InputError("%s must stay within the repository" % label)
    return path


def read_run_config(run_dir):
    run_path = repo_path(run_dir, "RUN_DIR")
    run_file = run_path / "run.json"
    config_file = run_path / "config" / "project.json"
    try:
        run = json.loads(run_file.read_text(encoding="utf-8"))
    except OSError as exc:
        raise InputError("cannot read run metadata %s: %s" % (run_file, exc))
    except json.JSONDecodeError as exc:
        raise InputError("invalid run metadata JSON: %s" % exc)
    if not isinstance(run, dict) or not isinstance(run.get("as_of_date"), str):
        raise InputError("run.json must contain an ISO as_of_date")
    try:
        as_of = dt.date.fromisoformat(run["as_of_date"])
    except ValueError:
        raise InputError("run.json as_of_date must be a valid YYYY-MM-DD date")

    try:
        project = json.loads(config_file.read_text(encoding="utf-8"))
    except OSError as exc:
        raise InputError("cannot read run config snapshot %s: %s" % (config_file, exc))
    except json.JSONDecodeError as exc:
        raise InputError("invalid project config snapshot JSON: %s" % exc)
    if not isinstance(project, dict):
        raise InputError("config/project.json snapshot must be a JSON object")
    window = project.get("freshness_window_days", 30)
    if isinstance(window, bool) or not isinstance(window, int) or window <= 0:
        raise InputError("freshness_window_days in the run snapshot must be a positive integer")
    return run_path, as_of, window


def active_source_ids(run_path):
    """Source IDs in the run's config snapshot, or None when the snapshot has no source list."""
    path = run_path / "config" / "sources.json"
    try:
        tiered = "include_backup" in json.loads((run_path / "run.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        tiered = False
    if not tiered or not path.is_file():
        return None  # only live runs record a tiered active source list
    try:
        sources = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InputError("cannot read run sources snapshot %s: %s" % (path, exc))
    if not isinstance(sources, list):
        raise InputError("config/sources.json snapshot must be a JSON array")
    return {x.get("source_id") for x in sources if isinstance(x, dict)}


def read_items():
    items = []
    for number, line in enumerate(sys.stdin, 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise InputError("line %d: malformed JSON: %s" % (number, exc))
        if not isinstance(item, dict):
            raise InputError("line %d: item must be a JSON object" % number)
        for key in ("item_id", "version_id", "published_at"):
            if key not in item:
                raise InputError("line %d: missing required field %s" % (number, key))
        if not isinstance(item["item_id"], str) or not item["item_id"]:
            raise InputError("line %d: item_id must be a nonempty string" % number)
        if not isinstance(item["version_id"], str) or not item["version_id"]:
            raise InputError("line %d: version_id must be a nonempty string" % number)
        if item["published_at"] is not None and not isinstance(item["published_at"], str):
            raise InputError("line %d: published_at must be a string or null" % number)
        items.append(item)
    return items


def publication_date(value):
    if value is None or value == "":
        return None, "unknown_date"
    try:
        if len(value) == 10:
            return dt.date.fromisoformat(value), None
        stamp = value[:-1] + "+00:00" if value.endswith("Z") else value
        parsed = dt.datetime.fromisoformat(stamp)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc).date(), None
    except (TypeError, ValueError, OverflowError):
        return None, "invalid_date"


def write_receipt(run_path, status, input_count, output_count, started, error=None):
    logs = run_path / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = logs / ("filter-%s-%d.json" % (stamp, os.getpid()))
    receipt = {
        "stage": "processing/filter_items.sh",
        "status": status,
        "input_count": input_count,
        "output_count": output_count,
        "started_at": started,
        "finished_at": utc_now(),
        "tools": ["Python standard library"],
        "cost_usd": None,
    }
    if error:
        receipt["errors"] = [error]
    with path.open("x", encoding="utf-8") as fh:
        json.dump(receipt, fh, ensure_ascii=False, sort_keys=True)
        fh.write("\n")


def run(run_dir):
    started = utc_now()
    run_path = repo_path(run_dir, "RUN_DIR")
    items = []
    try:
        run_path, as_of, window = read_run_config(run_dir)
        items = read_items()
        start_date = as_of - dt.timedelta(days=window - 1)
        active = active_source_ids(run_path)
        eligible = []
        exclusions = []
        ages = []
        for item in items:
            pub_date, error_reason = publication_date(item["published_at"])
            age_days = (as_of - pub_date).days if pub_date is not None else None
            reason = error_reason
            detail = ""
            if active is not None and item.get("source_id") not in active:
                reason = "inactive_source"
                detail = "Source %s is not in this run's active source list (backup tier or removed)." % item.get("source_id")
            elif error_reason == "unknown_date":
                detail = "Publication date is unknown; collection time is not used as a substitute."
            elif error_reason == "invalid_date":
                detail = "Publication date is not a valid ISO 8601 date or timestamp."
            elif pub_date is not None and pub_date > as_of:
                reason = "future_date"
                detail = "Publication date %s is after as-of date %s." % (pub_date.isoformat(), as_of.isoformat())
            elif pub_date is not None and pub_date < start_date:
                reason = "outside_window"
                detail = "Publication date %s is %d days before as-of date %s; window starts %s (%d days)." % (
                    pub_date.isoformat(), age_days, as_of.isoformat(), start_date.isoformat(), window
                )
            else:
                reason = None
            if reason == "inactive_source":
                age_days = None
            ages.append({"item_id": item["item_id"], "version_id": item["version_id"], "age_days": age_days})
            if reason:
                exclusions.append({
                    "item_id": item["item_id"],
                    "version_id": item["version_id"],
                    "reason": reason,
                    "detail": detail,
                })
            else:
                eligible.append(item)

        # Keep eligibility records byte-for-byte equivalent at the object level; age is recorded in its own sidecar.
        exclusions_path = run_path / "exclusions.jsonl"
        with exclusions_path.open("w", encoding="utf-8") as fh:
            for record in exclusions:
                fh.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        ages_path = run_path / "item_ages.jsonl"
        with ages_path.open("w", encoding="utf-8") as fh:
            for record in ages:
                fh.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        for item in eligible:
            print(json.dumps(item, ensure_ascii=False, separators=(",", ":")))
        write_receipt(run_path, "completed", len(items), len(eligible), started)
    except InputError as exc:
        try:
            write_receipt(run_path, "failed", len(items), 0, started, str(exc))
        except OSError:
            pass
        raise
    except OSError as exc:
        write_receipt(run_path, "failed", len(items), 0, started, str(exc))
        raise InputError("could not save filter artifacts: %s" % exc)


def main(argv):
    if len(argv) != 1:
        raise InputError("usage: filter_items.sh RUN_DIR")
    run(argv[0])


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except InputError as exc:
        print("processing/filter_items.sh: %s" % exc, file=sys.stderr)
        sys.exit(2)
    except OSError as exc:
        print("processing/filter_items.sh: filter stage failed: %s" % exc, file=sys.stderr)
        sys.exit(1)
