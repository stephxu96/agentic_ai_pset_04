#!/usr/bin/env python3
"""Deterministic checks for generated series artifacts and their evidence links."""

import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIECES = ("01", "02", "03")


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


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InputError("cannot read JSON %s: %s" % (path, exc))


def read_jsonl(path):
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise InputError("cannot read %s: %s" % (path, exc))
    records = []
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise InputError("invalid JSONL at %s:%d: %s" % (path, n, exc))
    return records


def file_bytes(path):
    try:
        return path.read_bytes()
    except OSError:
        return b"<missing>"


def issue(issues, severity, artifact, explanation, piece_id=None):
    record = {"severity": severity, "artifact": artifact, "explanation": explanation}
    if piece_id is not None:
        record["piece_id"] = piece_id
    issues.append(record)


def load_store_item(item_id, version_id):
    proc = subprocess.run(
        ["bash", "data/store.sh", "get", item_id, version_id], cwd=str(ROOT),
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def hash_inputs(run_path, run, briefs, manifests, issues):
    digest = hashlib.sha256()
    paths = ["run.json", "briefs.jsonl", "articles.jsonl", "video_scripts.jsonl", "eligible.jsonl"]
    for pid in PIECES:
        paths.extend(["articles/%s.md" % pid, "video_scripts/%s.md" % pid])
    for rel in paths:
        digest.update(rel.encode("utf-8") + b"\0")
        digest.update(file_bytes(run_path / rel) + b"\0")
    for brief in briefs:
        pid = brief.get("piece_id", "unknown")
        for claim in brief.get("claims", []):
            for ref in claim.get("evidence", []):
                item = load_store_item(ref.get("item_id"), ref.get("version_id"))
                if not item:
                    continue
                for field in ("text_path", "segments_path"):
                    rel = item.get(field)
                    if rel:
                        digest.update(rel.encode("utf-8") + b"\0")
                        digest.update(file_bytes(safe_path(rel)) + b"\0")
    return digest.hexdigest()


def count_words(text, folder="articles"):
    """Count publishable words: article body without references and claim markers, or video narration only."""
    if folder == "video_scripts":
        parts = re.findall(r"\*\*Narration:\*\*\s*(.*?)(?=\n\*\*Visual:\*\*|\Z)", text, flags=re.S)
        return len(" ".join(parts).split())
    body = re.split(r"\n##\s+References", text, maxsplit=1)[0]
    body = re.sub(r"[\[`]?\b\d\d-c\d+\b[\]`]?", "", body)
    return len(body.split())


def as_utc_date(value):
    if not isinstance(value, str):
        return None
    try:
        if len(value) == 10:
            return dt.date.fromisoformat(value)
        raw = value[:-1] + "+00:00" if value.endswith("Z") else value
        stamp = dt.datetime.fromisoformat(raw)
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=dt.timezone.utc)
        return stamp.astimezone(dt.timezone.utc).date()
    except (ValueError, OverflowError):
        return None


def check(run_dir):
    run_path = safe_path(run_dir)
    run = read_json(run_path / "run.json")
    if not isinstance(run, dict) or not isinstance(run.get("as_of_date"), str):
        raise InputError("run.json must contain as_of_date")
    try:
        as_of = dt.date.fromisoformat(run["as_of_date"])
    except ValueError:
        raise InputError("run.json contains an invalid as_of_date")
    project = read_json(run_path / "config" / "project.json")
    window = project.get("freshness_window_days", 30) if isinstance(project, dict) else None
    if isinstance(window, bool) or not isinstance(window, int) or window < 1:
        raise InputError("run config freshness_window_days must be a positive integer")
    start_date = as_of - dt.timedelta(days=window - 1)
    issues = []
    briefs = read_jsonl(run_path / "briefs.jsonl")
    article_manifest = read_jsonl(run_path / "articles.jsonl")
    script_manifest = read_jsonl(run_path / "video_scripts.jsonl")
    manifests = {"articles": article_manifest, "video_scripts": script_manifest}
    by_piece = {}

    if [b.get("piece_id") for b in briefs] != list(PIECES):
        issue(issues, "error", "briefs.jsonl", "Expected exactly one brief for pieces 01, 02, and 03.")
    briefs_by_piece = {b.get("piece_id"): b for b in briefs if isinstance(b, dict)}
    eligible_path = run_path / "eligible.jsonl"
    eligible = read_jsonl(eligible_path) if eligible_path.exists() else []
    eligible_by_version = {(x.get("item_id"), x.get("version_id")): x for x in eligible if isinstance(x, dict)}
    piece_publishers = {pid: set() for pid in PIECES}
    series_kinds = set()
    referenced_files = set()

    for kind, records in manifests.items():
        seen = set()
        for rec in records:
            pid = rec.get("piece_id") if isinstance(rec, dict) else None
            if pid not in PIECES:
                issue(issues, "error", kind + ".jsonl", "Manifest has an invalid piece_id.")
                continue
            if pid in seen:
                issue(issues, "error", kind + ".jsonl", "Duplicate manifest for piece %s." % pid, pid)
            seen.add(pid)
            by_piece.setdefault(pid, {})[kind] = rec
        if seen != set(PIECES):
            for missing in sorted(set(PIECES) - seen):
                issue(issues, "error", kind + ".jsonl", "Missing %s manifest for piece %s." % (kind, missing), missing)

    for pid in PIECES:
        brief = briefs_by_piece.get(pid)
        if not brief:
            continue
        claims = brief.get("claims")
        if not isinstance(claims, list) or not claims:
            issue(issues, "error", "briefs.jsonl", "Brief has no claims.", pid)
            continue
        known_claims = {c.get("claim_id") for c in claims if isinstance(c, dict)}
        for artifact_kind, folder in (("articles", "articles"), ("video_scripts", "video_scripts")):
            rec = by_piece.get(pid, {}).get(artifact_kind)
            if not rec:
                continue
            path_value = rec.get("path")
            try:
                draft_path = safe_path(path_value)
                text = draft_path.read_text(encoding="utf-8")
            except (InputError, OSError) as exc:
                issue(issues, "error", "%s/%s.md" % (folder, pid), "Missing or unreadable draft: %s" % exc, pid)
                continue
            if set(rec.get("claim_ids", [])) != known_claims:
                issue(issues, "error", "%s.jsonl" % artifact_kind,
                      "Manifest claim_ids do not match the brief's claims.", pid)
            for claim_id in known_claims:
                if claim_id and claim_id not in text:
                    issue(issues, "error", "%s/%s.md" % (folder, pid),
                          "Claim marker %s is missing from the draft." % claim_id, pid)
            word_count = count_words(text, folder)
            lower, upper = (600, 900) if folder == "articles" else (450, 750)
            if not lower <= word_count <= upper:
                issue(issues, "warning", "%s/%s.md" % (folder, pid),
                      "Draft has %d %s words; the approximate target is %d-%d words." % (word_count, "narration" if folder == "video_scripts" else "body", lower, upper), pid)

        for claim in claims:
            if not isinstance(claim, dict) or not claim.get("claim_id"):
                issue(issues, "error", "briefs.jsonl", "Claim is malformed or has no claim_id.", pid)
                continue
            refs = claim.get("evidence")
            if not isinstance(refs, list) or not refs:
                issue(issues, "error", "briefs.jsonl", "Claim %s has no evidence." % claim["claim_id"], pid)
                continue
            for ref in refs:
                if not isinstance(ref, dict):
                    issue(issues, "error", "briefs.jsonl", "Evidence reference is malformed.", pid)
                    continue
                key = (ref.get("item_id"), ref.get("version_id"))
                item = load_store_item(*key)
                if item is None:
                    issue(issues, "error", "briefs.jsonl", "Evidence item/version does not resolve in the store.", pid)
                    continue
                publisher = item.get("publisher_id")
                if publisher:
                    piece_publishers[pid].add(publisher)
                series_kinds.add(item.get("kind"))
                if key not in eligible_by_version:
                    issue(issues, "error", "briefs.jsonl", "Evidence is not present in this run's eligible corpus.", pid)
                published = as_utc_date(item.get("published_at"))
                if published is None or published < start_date or published > as_of:
                    issue(issues, "error", "briefs.jsonl", "Evidence date is unknown or outside this run's freshness window.", pid)
                loc = ref.get("locator", {})
                if loc.get("type") == "text":
                    try:
                        source_path = safe_path(item.get("text_path"))
                        referenced_files.add(source_path)
                        body = source_path.read_text(encoding="utf-8")
                    except (InputError, OSError) as exc:
                        issue(issues, "error", "briefs.jsonl", "Source text is unavailable: %s" % exc, pid)
                        continue
                    if not isinstance(loc.get("quote"), str) or loc["quote"] not in body:
                        issue(issues, "error", "briefs.jsonl", "Claim locator quote does not appear in source text.", pid)
                elif loc.get("type") == "segment":
                    try:
                        segment_path = safe_path(item.get("segments_path"))
                        referenced_files.add(segment_path)
                        segments = read_json(segment_path)
                        ids = {seg.get("segment_id") for seg in segments if isinstance(seg, dict)}
                    except (InputError, OSError, TypeError) as exc:
                        issue(issues, "error", "briefs.jsonl", "Transcript segments are unavailable: %s" % exc, pid)
                        continue
                    if loc.get("segment_id") not in ids:
                        issue(issues, "error", "briefs.jsonl", "Claim locator references an unknown transcript segment.", pid)
                else:
                    issue(issues, "error", "briefs.jsonl", "Evidence locator type must be text or segment.", pid)

        if len(piece_publishers[pid]) < 3:
            issue(issues, "error", "briefs.jsonl", "Piece %s has evidence from fewer than three independent publishers." % pid, pid)

    if not {"feed", "youtube", "podcast"}.issubset(series_kinds):
        missing = sorted({"feed", "youtube", "podcast"} - series_kinds)
        issue(issues, "error", "briefs.jsonl", "Series evidence is missing required input kind(s): %s." % ", ".join(missing))

    review_id = hash_inputs(run_path, run, briefs, manifests, issues)
    result = {"review_id": review_id, "passed": not any(x["severity"] == "error" for x in issues), "issues": issues}
    (run_path / "review.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def receipt(run_path, started, status, output_count, error=None):
    logs = run_path / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    rec = {"stage": "review/check_content.sh", "status": status, "input_count": None,
           "output_count": output_count, "started_at": started, "finished_at": utc_now(),
           "tools": ["Python standard library", "data/store.sh get"], "cost_usd": None}
    if error:
        rec["errors"] = [error]
    with (logs / ("check-content-%s-%d.json" % (stamp, os.getpid()))).open("x", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, sort_keys=True)
        fh.write("\n")


def main(argv):
    if len(argv) != 1:
        raise InputError("usage: check_content.sh RUN_DIR")
    started = utc_now()
    run_path = safe_path(argv[0])
    try:
        result = check(argv[0])
    except InputError as exc:
        receipt(run_path, started, "failed", 0, str(exc))
        raise
    receipt(run_path, started, "completed", 1)
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except InputError as exc:
        print("review/check_content.sh: %s" % exc, file=sys.stderr)
        sys.exit(2)
    except OSError as exc:
        print("review/check_content.sh: assessment failed: %s" % exc, file=sys.stderr)
        sys.exit(1)
