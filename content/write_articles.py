#!/usr/bin/env python3
"""Generate article drafts from reviewed briefs and their exact evidence versions."""

import datetime as dt
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from codex_jsonl import CodexError, invoke, write_jsonl  # noqa: E402


class InputError(Exception): pass


def safe_path(rel):
    if not isinstance(rel, str) or not rel or os.path.isabs(rel): raise InputError("expected repository-relative path")
    path = (ROOT / rel).resolve()
    if path != ROOT and ROOT not in path.parents: raise InputError("path escapes repository")
    return path


def read_json(path):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc: raise InputError("cannot read %s: %s" % (path, exc))


def read_input():
    rows = []
    for n, line in enumerate(sys.stdin, 1):
        if not line.strip(): continue
        try: rec = json.loads(line)
        except json.JSONDecodeError as exc: raise InputError("stdin line %d is not JSON: %s" % (n, exc))
        if not isinstance(rec, dict): raise InputError("stdin line %d must be an object" % n)
        rows.append(rec)
    return rows


def cited_text_excerpt(body, quotes):
    """Keep the lead and context around each exact locator, not an entire long page."""
    spans = [(0, min(len(body), 4000))]
    for quote in quotes:
        at = body.find(quote)
        if at < 0:
            raise InputError("brief quote is absent from retained source text: %r" % quote[:120])
        spans.append((max(0, at - 700), min(len(body), at + len(quote) + 700)))
    spans.sort()
    merged = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return "\n[... uncited source text omitted ...]\n".join(body[start:end] for start, end in merged)


def cited_segments(segments, segment_ids):
    """Include cited media segments and nearby context with their timestamps."""
    by_id = {segment.get("segment_id"): index for index, segment in enumerate(segments)
             if isinstance(segment, dict)}
    missing = segment_ids - by_id.keys()
    if missing:
        raise InputError("brief references missing transcript segment(s): %s" % ", ".join(sorted(missing)))
    selected = set()
    for segment_id in segment_ids:
        at = by_id[segment_id]
        selected.update(range(max(0, at - 2), min(len(segments), at + 3)))
    return [segments[index] for index in sorted(selected)]


def source_evidence(run_path, brief, eligible):
    records, locators = [], {}
    for claim in brief.get("claims", []):
        for ref in claim.get("evidence", []):
            key = (ref.get("item_id"), ref.get("version_id"))
            locators.setdefault(key, []).append(ref.get("locator", {}))
    for key, refs in locators.items():
        item = eligible.get(key)
        if not item: raise InputError("brief references an item/version not in eligible.jsonl: %s" % (key,))
        row = {k: item.get(k) for k in ("item_id", "version_id", "publisher_id", "kind", "title", "url", "published_at", "text_path", "segments_path")}
        body = safe_path(item["text_path"]).read_text(encoding="utf-8")
        if item.get("segments_path"):
            segments = read_json(safe_path(item["segments_path"]))
            ids = {ref.get("segment_id") for ref in refs if ref.get("type") == "segment"}
            row["segments"] = cited_segments(segments, ids)
            row["segments_total"] = len(segments)
            row["text"] = None
        else:
            quotes = [ref.get("quote") for ref in refs if ref.get("type") == "text"]
            if not quotes or any(not isinstance(quote, str) or not quote for quote in quotes):
                raise InputError("written evidence needs exact cited quotes: %s" % (key,))
            row["text"] = cited_text_excerpt(body, quotes)
            row["text_total_chars"] = len(body)
            row["segments"] = None
        records.append(row)
    return records


def validate_article(rec, brief, evidence):
    if rec.get("piece_id") != brief.get("piece_id"): return "article response piece_id does not match its brief"
    markdown = rec.get("markdown")
    if not isinstance(markdown, str) or not markdown.strip(): return "article markdown must be a nonempty string"
    for claim in brief.get("claims", []):
        if claim.get("claim_id") not in markdown: return "article is missing claim marker %s" % claim.get("claim_id")
    for item in evidence:
        if item.get("title") and item["title"] not in markdown:
            return "article references must include source title %s" % item["title"]
    return None


def main_run(run_dir):
    run_path = safe_path(run_dir)
    briefs = read_input()
    if [b.get("piece_id") for b in briefs] != ["01", "02", "03"]:
        raise InputError("stdin must contain exactly briefs 01, 02, and 03 in order")
    try:
        instructions = (run_path / "prompts" / "write_articles.md").read_text(encoding="utf-8")
        policy = (run_path / "config" / "editorial_policy.md").read_text(encoding="utf-8")
        run_meta = read_json(run_path / "run.json")
        eligible_records = [json.loads(line) for line in (run_path / "eligible.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as exc: raise InputError("missing or invalid run input: %s" % exc)
    eligible = {(it.get("item_id"), it.get("version_id")): it for it in eligible_records if isinstance(it, dict)}
    results = []
    for brief in briefs:
        evidence = source_evidence(run_path, brief, eligible)
        prompt = (instructions + "\n\nEDITORIAL POLICY\n" + policy + "\n\nAS-OF DATE\n" + str(run_meta.get("as_of_date")) +
                  "\n\nBRIEF\n" + json.dumps(brief, ensure_ascii=False) +
                  "\n\nVERSIONED EVIDENCE EXCERPTS\n" + write_jsonl(evidence) +
                  "\nThese excerpts include each cited passage or timestamp with nearby context, plus the written source lead; non-contiguous text is marked. Full retained assets remain at each text_path or segments_path. Do not infer omitted material.\n" +
                  "\n\nReturn exactly one JSONL object with fields piece_id and markdown. Put the complete requested article Markdown in markdown as a JSON string. "
                  "Return no extra keys, code fences around the JSONL, or commentary.")
        validator = lambda rec, _i, b=brief, ev=evidence: validate_article(rec, b, ev)
        rows = invoke(run_path, "content/write_articles.sh", prompt, validator=validator,
                      batch_validator=lambda rs: None if len(rs) == 1 else "expected one article record",
                      input_count=len(evidence))
        results.append(rows[0])
    article_dir = run_path / "articles"
    article_dir.mkdir(parents=True, exist_ok=True)
    manifests = []
    for brief, result in zip(briefs, results):
        pid = brief["piece_id"]
        target = article_dir / (pid + ".md")
        target.write_text(result["markdown"].rstrip() + "\n", encoding="utf-8")
        manifests.append({"piece_id": pid, "path": str(target.relative_to(ROOT)),
                          "claim_ids": [claim["claim_id"] for claim in brief["claims"]]})
    sys.stdout.write(write_jsonl(manifests))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2: raise InputError("usage: write_articles.sh RUN_DIR")
        main_run(sys.argv[1])
    except InputError as exc:
        print("content/write_articles.sh: %s" % exc, file=sys.stderr); sys.exit(2)
    except CodexError as exc:
        print("content/write_articles.sh: %s" % exc, file=sys.stderr); sys.exit(1)
    except OSError as exc:
        print("content/write_articles.sh: could not save drafts: %s" % exc, file=sys.stderr); sys.exit(1)
