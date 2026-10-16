#!/usr/bin/env python3
"""Generate three video scripts from the exact article briefs and evidence."""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
from codex_jsonl import CodexError, invoke, write_jsonl  # noqa: E402
from content.write_articles import InputError as EvidenceInputError, source_evidence  # noqa: E402


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


def validate_script(rec, brief, evidence):
    if rec.get("piece_id") != brief.get("piece_id"): return "script piece_id does not match the brief"
    markdown = rec.get("markdown")
    if not isinstance(markdown, str) or not markdown.strip(): return "script markdown must be nonempty"
    for claim in brief.get("claims", []):
        if claim.get("claim_id") not in markdown: return "script is missing claim marker %s" % claim.get("claim_id")
    for item in evidence:
        if item.get("title") and item["title"] not in markdown:
            return "script source-on-screen citations must include title %s" % item["title"]
    return None


def main_run(run_dir):
    run_path = safe_path(run_dir)
    briefs = read_input()
    if [b.get("piece_id") for b in briefs] != ["01", "02", "03"]:
        raise InputError("stdin must contain exactly briefs 01, 02, and 03 in order")
    try:
        instructions = (run_path / "prompts" / "write_video_scripts.md").read_text(encoding="utf-8")
        policy = (run_path / "config" / "editorial_policy.md").read_text(encoding="utf-8")
        run_meta = read_json(run_path / "run.json")
        eligible_rows = [json.loads(line) for line in (run_path / "eligible.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as exc: raise InputError("missing or invalid run input: %s" % exc)
    eligible = {(it.get("item_id"), it.get("version_id")): it for it in eligible_rows if isinstance(it, dict)}
    outputs = []
    for brief in briefs:
        evidence = source_evidence(run_path, brief, eligible)
        article_path = run_path / "articles" / (brief["piece_id"] + ".md")
        article_context = article_path.read_text(encoding="utf-8") if article_path.exists() else "No article draft is available yet."
        prompt = (instructions + "\n\nEDITORIAL POLICY\n" + policy + "\n\nAS-OF DATE\n" + str(run_meta.get("as_of_date")) +
                  "\n\nBRIEF\n" + json.dumps(brief, ensure_ascii=False) +
                  "\n\nCOMPANION ARTICLE DRAFT (align claims; follow the brief and evidence if it conflicts)\n" + article_context +
                  "\n\nVERSIONED EVIDENCE EXCERPTS\n" + write_jsonl(evidence) +
                  "\nThese excerpts include each cited passage or timestamp with nearby context, plus the written source lead; non-contiguous text is marked. Full retained assets remain at each text_path or segments_path. Do not infer omitted material.\n" +
                  "\n\nReturn exactly one JSONL object with fields piece_id and markdown. Put the complete scene-by-scene script Markdown in markdown as a JSON string. "
                  "Return no extra keys, fences around the JSONL record, or commentary.")
        validator = lambda rec, _idx, b=brief, ev=evidence: validate_script(rec, b, ev)
        records = invoke(run_path, "content/write_video_scripts.sh", prompt, validator=validator,
                         batch_validator=lambda rs: None if len(rs) == 1 else "expected one script record",
                         input_count=len(evidence))
        outputs.append(records[0])
    output_dir = run_path / "video_scripts"
    output_dir.mkdir(parents=True, exist_ok=True)
    manifests = []
    for brief, result in zip(briefs, outputs):
        pid = brief["piece_id"]
        target = output_dir / (pid + ".md")
        target.write_text(result["markdown"].rstrip() + "\n", encoding="utf-8")
        manifests.append({"piece_id": pid, "path": str(target.relative_to(ROOT)),
                          "claim_ids": [claim["claim_id"] for claim in brief["claims"]]})
    sys.stdout.write(write_jsonl(manifests))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2: raise InputError("usage: write_video_scripts.sh RUN_DIR")
        main_run(sys.argv[1])
    except (InputError, EvidenceInputError) as exc:
        print("content/write_video_scripts.sh: %s" % exc, file=sys.stderr); sys.exit(2)
    except CodexError as exc:
        print("content/write_video_scripts.sh: %s" % exc, file=sys.stderr); sys.exit(1)
    except OSError as exc:
        print("content/write_video_scripts.sh: could not save scripts: %s" % exc, file=sys.stderr); sys.exit(1)
