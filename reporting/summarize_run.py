#!/usr/bin/env python3
"""Summarize run artifacts, coverage, receipts, and remaining production work."""

import datetime as dt
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COUNT_FILES = {
    "discovered": ("candidates.jsonl", "distinct"),
    "extracted": ("items.jsonl", "distinct"),
    "new": ("changes.jsonl", "change:new"),
    "changed": ("changes.jsonl", "change:changed"),
    "unchanged": ("changes.jsonl", "change:unchanged"),
    "eligible": ("eligible.jsonl", "distinct"),
    "excluded": ("exclusions.jsonl", "distinct"),
    "accepted": ("decisions.jsonl", "decision:accept"),
    "rejected": ("decisions.jsonl", "decision:reject"),
    "deferred": ("decisions.jsonl", "decision:defer"),
}


class InputError(Exception):
    pass


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def safe_path(rel):
    if not isinstance(rel, str) or not rel or os.path.isabs(rel):
        raise InputError("expected a repository-relative path")
    path = (ROOT / rel).resolve()
    if path != ROOT and ROOT not in path.parents:
        raise InputError("path escapes the repository: %s" % rel)
    return path


def json_file(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def jsonl_file(path):
    if not path.exists():
        return None
    result = []
    try:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                result.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise InputError("invalid JSONL at %s:%d: %s" % (path, number, exc))
    except OSError as exc:
        raise InputError("cannot read %s: %s" % (path, exc))
    return result


def records_for(run_path, name):
    return jsonl_file(run_path / name)


def count_artifact(run_path, filename, mode):
    records = records_for(run_path, filename)
    if records is None:
        return None
    if mode == "distinct":
        return len({r.get("item_id") for r in records if isinstance(r, dict)})
    field, value = mode.split(":", 1)
    return sum(1 for r in records if isinstance(r, dict) and r.get(field) == value)


def flatten_receipts(run_path):
    logs = run_path / "logs"
    if not logs.is_dir():
        return []
    results = []
    for path in sorted(logs.iterdir()):
        if not path.is_file() or path.suffix.lower() != ".json":
            continue
        rec = json_file(path)
        if isinstance(rec, dict):
            results.append(rec)
    return results


def find_values(obj, contains):
    found = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if contains in str(key).lower():
                found.append(value)
            found.extend(find_values(value, contains))
    elif isinstance(obj, list):
        for value in obj:
            found.extend(find_values(value, contains))
    return found


def parse_time(value):
    if not isinstance(value, str):
        return None
    try:
        raw = value[:-1] + "+00:00" if value.endswith("Z") else value
        stamp = dt.datetime.fromisoformat(raw)
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=dt.timezone.utc)
        return stamp.astimezone(dt.timezone.utc)
    except ValueError:
        return None


def summarize(run_path):
    run = json_file(run_path / "run.json")
    if not isinstance(run, dict) or not isinstance(run.get("run_id"), str):
        raise InputError("run directory must contain run.json with run_id")
    counts = {name: count_artifact(run_path, filename, mode)
              for name, (filename, mode) in COUNT_FILES.items()}
    article_manifest = records_for(run_path, "articles.jsonl")
    script_manifest = records_for(run_path, "video_scripts.jsonl")
    counts["articles"] = len(article_manifest) if article_manifest is not None else None
    counts["video_scripts"] = len(script_manifest) if script_manifest is not None else None

    candidate_records = records_for(run_path, "candidates.jsonl")
    duplicates = 0
    observations = 0 if candidate_records is not None else None
    if candidate_records is not None:
        candidate_ids = [r.get("item_id") for r in candidate_records if isinstance(r, dict)]
        observations = len(candidate_ids)
        duplicates = observations - len(set(candidate_ids))

    evidence = records_for(run_path, "eligible.jsonl")
    if evidence is None:
        evidence = records_for(run_path, "items.jsonl")
    by_kind = {kind: {"items": 0, "publishers": []} for kind in ("feed", "youtube", "podcast")}
    publishers = set()
    kind_seen = {kind: set() for kind in by_kind}
    if evidence is not None:
        for item in evidence:
            if not isinstance(item, dict):
                continue
            kind = item.get("kind")
            item_id = item.get("item_id")
            publisher_id = item.get("publisher_id")
            if kind in by_kind and item_id not in kind_seen[kind]:
                kind_seen[kind].add(item_id)
                if publisher_id:
                    by_kind[kind]["publishers"].append(publisher_id)
                    publishers.add(publisher_id)
        for kind in by_kind:
            by_kind[kind]["items"] = len(kind_seen[kind])
            by_kind[kind]["publishers"] = sorted(set(by_kind[kind]["publishers"]))

    receipts = flatten_receipts(run_path)
    failed_stages = []
    for rec in receipts:
        status = find_values(rec, "status")
        stages = find_values(rec, "stage")
        if any(str(s).lower() in ("failed", "error") for s in status):
            failed_stages.append({"stage": stages[0] if stages else "unknown stage", "status": "failed"})
    tools = sorted({str(v) for rec in receipts for v in find_values(rec, "tool") if isinstance(v, (str, int, float))})
    models = sorted({str(v) for rec in receipts for v in find_values(rec, "model") if isinstance(v, (str, int, float))})
    costs = [v for rec in receipts for v in find_values(rec, "cost")
             if isinstance(v, (int, float)) and not isinstance(v, bool)]
    unknown_costs = sum(1 for rec in receipts if any(v is None for v in find_values(rec, "cost")))

    started = parse_time(run.get("started_at"))
    # Elapsed time ends when the run's workflows finish; later re-checks and packaging do not extend it.
    workflow_receipts = [rec for rec in receipts
                         if any(str(st).startswith("workflows/") for st in find_values(rec, "stage"))]
    finishes = [parse_time(v) for rec in (workflow_receipts or receipts) for v in find_values(rec, "finish")]
    finishes = [v for v in finishes if v is not None]
    if started and finishes:
        elapsed_seconds = max(0, int((max(finishes) - started).total_seconds()))
    else:
        elapsed_seconds = None

    review = json_file(run_path / "review.json")
    approval = json_file(run_path / "approval.json")
    package_manifest = json_file(run_path / "package" / "manifest.json")
    ready = bool(review and review.get("passed") is True and approval and
                 approval.get("decision") == "approve" and
                 approval.get("review_id") == review.get("review_id") and package_manifest)
    if failed_stages or (review is not None and review.get("passed") is False):
        status = "failed"
    elif review is not None:
        status = "ready_for_production" if ready else "awaiting_review"
    elif run.get("mode") == "replay":
        # A replay deliberately stops before drafting; the absence of a review is not a failure.
        status = "awaiting_review"
    else:
        status = "failed"

    links = json_file(run_path / "package" / "publication_links.json")
    if isinstance(links, dict):
        links = links.get("pieces", [])
    links = links if isinstance(links, list) else []
    published_links = [r for r in links if isinstance(r, dict) and r.get("substack_url") and r.get("youtube_url")]
    manual_actions = []
    if counts["articles"] != 3 or counts["video_scripts"] != 3:
        manual_actions.append("Complete and review the three article and video-script drafts.")
    if not package_manifest:
        manual_actions.append("Complete human editorial review and prepare the production package.")
    if counts["video_scripts"] == 3 and len(published_links) < 3:
        manual_actions.append("Build the three slide decks, generate the Chatterbox voiceover, then render and review the videos.")
    if len(published_links) < 3:
        manual_actions.extend(["Publish the articles on Substack and record their URLs.",
                               "Upload the videos to YouTube, add article/source references, and record their URLs.",
                               "Verify that course staff can access all six publication links."])

    if run.get("mode") == "replay":
        manual_actions = ["This is a labeled replay (as-of %s), not a live run. It produces no publication; "
                          "report it as a replay and do not count it as one of the two live runs."
                          % run.get("as_of_date")]
    return {
        "run_id": run["run_id"],
        "mode": run.get("mode"),
        "status": status,
        "as_of_date": run.get("as_of_date"),
        "counts": counts,
        "duplicate_observations": {"candidate_observations": observations, "duplicates": duplicates},
        "source_coverage": {"by_kind": by_kind, "independent_publisher_count": len(publishers),
                            "independent_publishers": sorted(publishers)},
        "failed_stages": failed_stages,
        "elapsed_seconds": elapsed_seconds,
        "tools": tools,
        "models": models,
        "known_cost_usd": sum(costs) if costs else None,
        "unknown_cost_stage_count": unknown_costs if receipts else None,
        "published_links": published_links,
        "remaining_manual_actions": manual_actions,
    }


def save_receipt(run_path, started, result):
    logs = run_path / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    receipt = {"stage": "reporting/summarize_run.sh", "status": "completed",
               "input_count": len(flatten_receipts(run_path)), "output_count": 1,
               "started_at": started, "finished_at": utc_now(),
               "tools": ["Python standard library"], "cost_usd": None}
    with (logs / ("summary-%s-%d.json" % (stamp, os.getpid()))).open("x", encoding="utf-8") as fh:
        json.dump(receipt, fh, ensure_ascii=False, sort_keys=True)
        fh.write("\n")
    (run_path / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv):
    if len(argv) != 1:
        raise InputError("usage: summarize_run.sh RUN_DIR")
    run_path = safe_path(argv[0])
    if not run_path.is_dir():
        raise InputError("RUN_DIR does not exist")
    started = utc_now()
    result = summarize(run_path)
    save_receipt(run_path, started, result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except InputError as exc:
        print("reporting/summarize_run.sh: %s" % exc, file=sys.stderr)
        sys.exit(2)
    except OSError as exc:
        print("reporting/summarize_run.sh: summary failed: %s" % exc, file=sys.stderr)
        sys.exit(1)
