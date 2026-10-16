#!/usr/bin/env python3
"""Select eligible items in small batches using the snapshotted policy and prompt."""

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from codex_jsonl import CodexError, invoke, write_jsonl  # noqa: E402


class InputError(Exception): pass


def safe_path(rel):
    if not isinstance(rel, str) or not rel or os.path.isabs(rel): raise InputError("expected a repository-relative path")
    path = (ROOT / rel).resolve()
    if path != ROOT and ROOT not in path.parents: raise InputError("path escapes the repository: %s" % rel)
    return path


def utc_now(): return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


SIGNAL_TERMS = ("cad", "3d", "geometr", "spatial", "parametric", "simulation",
                "benchmark", "evaluat", "trial", "tested", "success", "fail",
                "robot", "manufactur", "verification", "grader", "task")
TITLE_STOPWORDS = {"about", "after", "before", "from", "into", "models", "their",
                   "there", "these", "this", "those", "with", "without"}


def batch_excerpt(item, maximum=None):
    try:
        path = safe_path(item["text_path"])
        text = path.read_text(encoding="utf-8", errors="replace")
    except (KeyError, OSError, InputError) as exc:
        raise InputError("evidence text unavailable for %s: %s" % (item.get("item_id"), exc))
    if maximum is None:
        maximum = 6000 if item.get("kind") == "feed" else 1200
    return text[:maximum]


def load_selection_checks(run_path, eligible):
    path = run_path / "selection_checks.jsonl"
    if not path.exists(): return {}
    allowed = {(item["item_id"], item["version_id"]) for item in eligible}
    checks = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise InputError("cannot read selection checks: %s" % exc)
    for number, line in enumerate(lines, 1):
        if not line.strip(): continue
        try: record = json.loads(line)
        except json.JSONDecodeError as exc: raise InputError("selection checks line %d is not JSON: %s" % (number, exc))
        if not isinstance(record, dict): raise InputError("selection checks line %d must be an object" % number)
        key = (record.get("item_id"), record.get("version_id"))
        if key not in allowed:
            print("select_items: ignoring selection check for an item/version outside this run: %s" % (key,), file=sys.stderr)
            continue
        if key in checks: raise InputError("selection checks line %d duplicates an item/version" % number)
        entries = record.get("checks")
        if not isinstance(entries, list) or not entries: raise InputError("selection checks line %d needs checks" % number)
        for entry in entries:
            if not isinstance(entry, dict) or any(not isinstance(entry.get(field), str) or not entry[field].strip()
                                                  for field in ("url", "confirmed", "limitations")):
                raise InputError("selection checks line %d has an incomplete check" % number)
            if not entry["url"].startswith("https://"):
                raise InputError("selection checks line %d needs an HTTPS source URL" % number)
        checks[key] = entries
    return checks


def timestamp(seconds):
    total = max(0, int(float(seconds)))
    return "%02d:%02d:%02d" % (total // 3600, (total // 60) % 60, total % 60)


def sampled_segments(item):
    try:
        segments = json.loads(safe_path(item["segments_path"]).read_text(encoding="utf-8"))
    except (KeyError, OSError, ValueError, InputError) as exc:
        raise InputError("timestamped transcript unavailable for %s: %s" % (item.get("item_id"), exc))
    if not isinstance(segments, list) or not segments:
        raise InputError("timestamped transcript is empty for %s" % item.get("item_id"))
    title_terms = {word for word in re.findall(r"[a-z0-9]+", item.get("title", "").lower())
                   if len(word) >= 4 and word not in TITLE_STOPWORDS}
    scored = []
    for index, segment in enumerate(segments):
        if not isinstance(segment, dict) or not isinstance(segment.get("text"), str):
            raise InputError("invalid transcript segment for %s" % item.get("item_id"))
        body = segment["text"].lower()
        score = sum(3 for term in title_terms if term in body)
        score += sum(2 for term in SIGNAL_TERMS if term in body)
        scored.append((score, index))
    if len(segments) <= 48:
        chosen = range(len(segments))
    else:
        chosen_set = {i * (len(segments) - 1) // 11 for i in range(12)}
        for _, index in sorted(scored, key=lambda pair: (-pair[0], pair[1]))[:12]:
            chosen_set.update(i for i in (index - 1, index, index + 1) if 0 <= i < len(segments))
        chosen = sorted(chosen_set)
    return {
        "transcript_segments_total": len(segments),
        "transcript_segments_sampled": len(chosen),
        "transcript_segments": [
            {"segment_id": segments[i].get("segment_id"),
             "start_seconds": segments[i].get("start_seconds"),
             "timestamp": timestamp(segments[i].get("start_seconds", 0)),
             "text": segments[i]["text"]} for i in chosen
        ],
    }


def validate_batch(records, expected):
    expected_by = {(r["item_id"], r["version_id"]): r for r in expected}
    seen = set()
    for rec in records:
        key = (rec.get("item_id"), rec.get("version_id"))
        if key not in expected_by: return "response includes an item/version outside this batch"
        if key in seen: return "response repeats an item/version"
        seen.add(key)
        if rec.get("decision") not in ("accept", "reject", "defer"): return "decision must be accept, reject, or defer"
        if not isinstance(rec.get("reason"), str) or not rec["reason"].strip(): return "each decision needs a nonempty reason"
        pids = rec.get("piece_ids")
        if not isinstance(pids, list) or any(p not in ("01", "02", "03") for p in pids): return "piece_ids must contain only 01, 02, or 03"
        if rec["decision"] == "accept" and not pids: return "accepted items need intended piece_ids"
        if rec["decision"] != "accept" and pids: return "rejected and deferred items need an empty piece_ids array"
    if seen != set(expected_by): return "response must contain exactly one decision for each batch item"
    return None


def run(run_dir):
    run_path = safe_path(run_dir)
    rows = []
    for number, line in enumerate(sys.stdin, 1):
        if not line.strip(): continue
        try: rec = json.loads(line)
        except json.JSONDecodeError as exc: raise InputError("stdin line %d is not JSON: %s" % (number, exc))
        if not isinstance(rec, dict) or not isinstance(rec.get("item_id"), str) or not isinstance(rec.get("version_id"), str):
            raise InputError("stdin line %d is missing item_id or version_id" % number)
        rows.append(rec)
    try:
        policy = (run_path / "config" / "editorial_policy.md").read_text(encoding="utf-8")
        instructions = (run_path / "prompts" / "select_items.md").read_text(encoding="utf-8")
    except OSError as exc: raise InputError("missing prompt or policy snapshot: %s" % exc)
    if not policy.strip() or not instructions.strip(): raise InputError("prompt and editorial policy snapshots must be nonempty")
    external_checks = load_selection_checks(run_path, rows)
    decisions = []
    # One item per call prevents long evidence excerpts from crowding out
    # decisions for other items in the same response.
    for start in range(0, len(rows), 1):
        batch = rows[start:start + 1]
        input_rows = []
        for item in batch:
            input_rows.append({key: item.get(key) for key in (
                "item_id", "version_id", "source_id", "publisher_id", "kind", "title", "url", "published_at")})
            input_rows[-1]["excerpt"] = batch_excerpt(item)
            if item.get("kind") in ("youtube", "podcast"):
                input_rows[-1].update(sampled_segments(item))
            checks = external_checks.get((item["item_id"], item["version_id"]))
            if checks:
                input_rows[-1]["external_checks"] = checks
        prompt = (instructions + "\n\nEDITORIAL POLICY\n" + policy +
                  "\n\nEligible item batch (JSON records):\n" + write_jsonl(input_rows) +
                  "\nMedia transcript_segments are timestamped, non-contiguous samples from the full retained transcript. "
                  "They include relevant and time-spread passages; do not claim that an item lacks timestamps when they are supplied. "
                  "Do not assume an omitted passage is absent from the full source, and do not treat automatic transcription alone as independent verification of a numerical claim. "
                  "External checks are separately sourced verification context, not an additional collected item or independent publisher. "
                  "Use their confirmed facts only within their stated limitations; do not promote a preview, demonstration, or simulation result into deployed performance. "
                  "\nReturn exactly one strict JSONL decision record for each input item, using the prompt's fields. "
                  "Return only JSONL, with no Markdown fences or commentary.")
        # Validate batch-level identity/count as well as each individual record.
        records = invoke(run_path, "editorial/select_items.sh", prompt,
                         validator=lambda rec, idx, b=batch: validate_one(rec, b[idx]) if idx < len(b) else "unexpected response record",
                         batch_validator=lambda recs, b=batch: validate_batch(recs, b), input_count=len(batch))
        decisions.extend(records)
    if not rows:
        write_empty_receipt(run_path, len(rows))
    sys.stdout.write(write_jsonl(decisions))


def validate_one(rec, expected):
    return validate_batch([rec], [expected])


def write_empty_receipt(run_path, count):
    logs = run_path / "logs"; logs.mkdir(parents=True, exist_ok=True)
    name = "select-items-empty-%s.json" % dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    payload = {"stage": "editorial/select_items.sh", "status": "completed", "input_count": count,
               "output_count": 0, "started_at": utc_now(), "finished_at": utc_now(),
               "tools": ["Codex CLI (not invoked; no eligible items)"], "model": "default, name not reported", "cost_usd": None}
    with (logs / name).open("x", encoding="utf-8") as fh: json.dump(payload, fh, ensure_ascii=False); fh.write("\n")


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2: raise InputError("usage: select_items.sh RUN_DIR")
        run(sys.argv[1])
    except InputError as exc:
        print("editorial/select_items.sh: %s" % exc, file=sys.stderr); sys.exit(2)
    except CodexError as exc:
        print("editorial/select_items.sh: %s" % exc, file=sys.stderr); sys.exit(1)
