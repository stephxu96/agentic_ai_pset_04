#!/usr/bin/env python3
"""Build a production package only when current review and human approval match."""

import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIECES = ("01", "02", "03")


class InputError(Exception):
    pass


class ArgumentError(InputError):
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


def read_json(path, label):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise InputError("%s is missing or unreadable: %s" % (label, exc))
    except json.JSONDecodeError as exc:
        raise InputError("%s is invalid JSON: %s" % (label, exc))


def read_jsonl(path, label):
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise InputError("%s is missing or unreadable: %s" % (label, exc))
    records = []
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise InputError("%s line %d is invalid JSON: %s" % (label, line_number, exc))
    return records


def save_receipt(run_path, started, status, count, error=None):
    logs = run_path / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    rec = {"stage": "publishing/prepare_package.sh", "status": status,
           "input_count": count, "output_count": count if status == "completed" else 0,
           "started_at": started, "finished_at": utc_now(),
           "tools": ["Python standard library"], "cost_usd": None}
    if error:
        rec["errors"] = [error]
    with (logs / ("package-%s-%d.json" % (stamp, os.getpid()))).open("x", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, sort_keys=True)
        fh.write("\n")


def ensure_current_review(run_dir, run_path):
    proc = subprocess.run(["bash", "review/check_content.sh", run_dir], cwd=str(ROOT),
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise InputError("content check could not run: %s" % (proc.stderr.strip() or proc.stdout.strip()))
    try:
        fresh = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise InputError("content check did not emit review JSON")
    saved = read_json(run_path / "review.json", "review.json")
    if saved.get("review_id") != fresh.get("review_id"):
        raise InputError("reviewed inputs changed; rerun the review and obtain matching approval")
    if saved.get("passed") is not True or fresh.get("passed") is not True:
        raise InputError("a failing review cannot be approved into a package")
    return fresh


def package(run_dir):
    run_path = safe_path(run_dir)
    started = utc_now()
    copied = 0
    try:
        review = ensure_current_review(run_dir, run_path)
        approval = read_json(run_path / "approval.json", "approval.json")
        if approval.get("decision") != "approve":
            raise InputError("human approval decision is not approve")
        if approval.get("review_id") != review.get("review_id"):
            raise InputError("approval review_id does not match the current review")
        if not isinstance(approval.get("reviewer"), str) or not approval["reviewer"].strip():
            raise InputError("approval reviewer is missing")

        briefs = read_jsonl(run_path / "briefs.jsonl", "briefs.jsonl")
        articles = read_jsonl(run_path / "articles.jsonl", "articles.jsonl")
        scripts = read_jsonl(run_path / "video_scripts.jsonl", "video_scripts.jsonl")
        briefs_by_id = {b.get("piece_id"): b for b in briefs}
        article_by_id = {a.get("piece_id"): a for a in articles}
        script_by_id = {s.get("piece_id"): s for s in scripts}
        if any(pid not in briefs_by_id or pid not in article_by_id or pid not in script_by_id for pid in PIECES):
            raise InputError("package requires all three briefs, articles, and video scripts")

        package_dir = run_path / "package"
        package_dir.mkdir(parents=True, exist_ok=True)
        links_path = package_dir / "publication_links.json"
        if links_path.exists():
            links = read_json(links_path, "package/publication_links.json")
            if isinstance(links, dict):
                links = links.get("pieces", [])
        else:
            links = []
        links_by_piece = {r.get("piece_id"): r for r in links if isinstance(r, dict)}
        normalized_links = [
            {"piece_id": pid,
             "substack_url": links_by_piece.get(pid, {}).get("substack_url"),
             "youtube_url": links_by_piece.get(pid, {}).get("youtube_url")}
            for pid in PIECES
        ]

        assets = []
        for pid in PIECES:
            for kind, manifest in (("article", article_by_id[pid]), ("video_script", script_by_id[pid])):
                source = safe_path(manifest.get("path"))
                if not source.is_file():
                    raise InputError("missing %s for piece %s" % (kind, pid))
                subdir = "articles" if kind == "article" else "video_scripts"
                rel_dest = "%s/%s.md" % (subdir, pid)
                dest = package_dir / rel_dest
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(source.read_bytes())
                assets.append({"piece_id": pid, "type": kind, "path": "package/" + rel_dest})
                copied += 1

            brief = briefs_by_id[pid]
            notes = ["# Source notes for piece %s" % pid, "", "As of %s." % read_json(run_path / "run.json", "run.json").get("as_of_date", "unknown"), ""]
            seen = set()
            for claim in brief.get("claims", []):
                for ref in claim.get("evidence", []):
                    key = (ref.get("item_id"), ref.get("version_id"))
                    if key in seen:
                        continue
                    seen.add(key)
                    store = subprocess.run(["bash", "data/store.sh", "get", key[0], key[1]],
                                           cwd=str(ROOT), capture_output=True, text=True)
                    if store.returncode != 0:
                        raise InputError("source note evidence does not resolve: %s / %s" % key)
                    item = json.loads(store.stdout)
                    notes.append("- %s — %s, %s, %s (%s)." % (
                        item.get("title", "Untitled"), item.get("publisher_id", "unknown publisher"),
                        (item.get("published_at") or "undated")[:10], item.get("url", ""), key[1]))
            note_rel = "source_notes/%s.md" % pid
            note_path = package_dir / note_rel
            note_path.parent.mkdir(parents=True, exist_ok=True)
            note_path.write_text("\n".join(notes) + "\n", encoding="utf-8")
            assets.append({"piece_id": pid, "type": "source_notes", "path": "package/" + note_rel})
            copied += 1

        links_path.write_text(json.dumps(normalized_links, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        assets.append({"type": "publication_links", "path": "package/publication_links.json"})
        assets.append({"type": "manual_handoff", "path": "package/README.md"})
        manual = """# Production handoff

1. Build each video from the matching script and source notes: a PowerPoint deck with one slide per scene, a voiceover generated with Chatterbox from the author's voice sample, and the two combined into an MP4 with ffmpeg. Review each video before upload.
2. Publish each reviewed article on Substack and add the final URL to `publication_links.json`.
3. Upload each rendered video to YouTube, add the article and source references to its description, then add the video URL to `publication_links.json`.
4. Verify that all six publication links are accessible to course staff.

Package preparation does not render videos or publish content.
"""
        (package_dir / "README.md").write_text(manual, encoding="utf-8")
        manifest = {"review_id": review["review_id"], "approval_reviewer": approval["reviewer"], "assets": assets}
        (package_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        save_receipt(run_path, started, "completed", copied)
        print(json.dumps(manifest, ensure_ascii=False))
    except InputError as exc:
        save_receipt(run_path, started, "failed", copied, str(exc))
        raise
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        save_receipt(run_path, started, "failed", copied, str(exc))
        raise InputError("could not prepare package: %s" % exc)


def main(argv):
    if len(argv) != 1:
        raise ArgumentError("usage: prepare_package.sh RUN_DIR")
    package(argv[0])


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except ArgumentError as exc:
        print("publishing/prepare_package.sh: %s" % exc, file=sys.stderr)
        sys.exit(2)
    except InputError as exc:
        print("publishing/prepare_package.sh: %s" % exc, file=sys.stderr)
        sys.exit(1)
