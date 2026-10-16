#!/usr/bin/env python3
"""Validate the artifacts of a real run against ARCHITECTURE.md and the README minimums.

Usage (from the repo root):
    python3 tests/validate_run.py runs/RUN_ID
    python3 tests/validate_run.py runs/RUN_ID --no-store     # skip calling data/store.sh
    python3 tests/validate_run.py runs/RUN_ID --repo /path/to/repo

Exit code 1 if any ERROR is found. WARN items need your judgment. Standard library only.
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import contracts as C  # noqa: E402


class Report:
    def __init__(self):
        self.errors, self.warns, self.oks = [], [], []

    def err(self, m):
        self.errors.append(m)

    def warn(self, m):
        self.warns.append(m)

    def ok(self, m):
        self.oks.append(m)

    def section(self, title):
        print(f"\n== {title}")

    def flush(self, start=0):
        for kind, items in (("ERROR", self.errors), ("WARN ", self.warns), ("ok   ", self.oks)):
            for m in items:
                print(f"  [{kind}] {m}")
        self.errors, self.warns, self.oks = [], [], []


TOTALS = {"errors": 0, "warns": 0}
R = Report()


def finish_section(title):
    TOTALS["errors"] += len(R.errors)
    TOTALS["warns"] += len(R.warns)
    R.section(title)
    R.flush()


def read_text(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def read_jsonl(path):
    recs, problems = [], []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError as e:
                problems.append(f"{os.path.basename(path)} line {n}: invalid JSON ({e})")
    return recs, problems


def to_date(s):
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(dt.timezone.utc).date()
    except (ValueError, AttributeError):
        return None


def narration_only(text):
    parts = re.findall(r"\*\*Narration:\*\*\s*(.*?)(?=\n\*\*Visual:\*\*|\Z)", text, flags=re.S)
    return " ".join(parts)


def words(text):
    return len(re.findall(r"\b[\w'-]+\b", text))


def body_before_references(text):
    parts = re.split(r"\n#+\s*references\b", text, flags=re.I)
    return parts[0]


def norm_title(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--repo", default=os.path.dirname(HERE))
    ap.add_argument("--no-store", action="store_true")
    a = ap.parse_args()
    repo = os.path.abspath(a.repo)
    os.chdir(repo)
    rd = a.run_dir.rstrip("/")
    if not os.path.isdir(rd):
        print(f"run directory not found: {rd}")
        return 2
    P = lambda *p: os.path.join(rd, *p)  # noqa: E731

    # ---- run.json and snapshots ------------------------------------------------
    run = {}
    if not os.path.isfile(P("run.json")):
        R.err("run.json missing")
    else:
        run = read_json(P("run.json"))
        for k in ("run_id", "started_at", "as_of_date", "mode", "previous_run_id"):
            if k not in run:
                R.err(f"run.json missing '{k}'")
        if run.get("mode") not in ("live", "example", "replay"):
            R.err(f"run.json mode should be live, example or replay, got {run.get('mode')!r}")
        if run.get("run_id") and run["run_id"] != os.path.basename(rd):
            R.warn(f"run.json run_id {run['run_id']!r} differs from the directory name")
        if run.get("mode") == "live" and to_date(run.get("started_at", "")) and \
                to_date(run["started_at"]).isoformat() != run.get("as_of_date"):
            R.warn("live run: as_of_date differs from the UTC date of started_at (it must be the actual execution date)")
    as_of = None
    try:
        as_of = dt.date.fromisoformat(run.get("as_of_date", ""))
    except ValueError:
        R.err("as_of_date is missing or not YYYY-MM-DD; cannot check the window")
    project = {}
    for name in ("project.json", "sources.json", "editorial_policy.md"):
        if not os.path.isfile(P("config", name)):
            R.err(f"config snapshot missing: config/{name}")
    if os.path.isfile(P("config", "project.json")):
        project = read_json(P("config", "project.json"))
    for name in ("select_items", "create_briefs", "write_articles", "write_video_scripts"):
        if not os.path.isfile(P("prompts", name + ".md")):
            R.err(f"prompt snapshot missing: prompts/{name}.md")
    window = project.get("freshness_window_days", 30)
    if run.get("mode") == "live" and window != 30:
        R.warn(f"live run uses a {window}-day window; the assignment requires 30. Disclose this in SUBMISSION.md")
    if not R.errors:
        R.ok(f"run.json and config/prompts snapshots present (as-of {run.get('as_of_date')}, mode {run.get('mode')}, window {window} days)")
    finish_section("run.json and snapshots")

    # ---- record streams ------------------------------------------------------------
    def load(name, validator, label):
        path = P(name)
        if not os.path.isfile(path):
            R.warn(f"{name} not present (stage may not have run)")
            return None
        recs, problems = read_jsonl(path)
        for pr in problems:
            R.err(pr)
        bad = 0
        for i, r in enumerate(recs):
            for pr in validator(r, f"{name}[{i}]"):
                R.err(pr)
                bad += 1
        if not problems and not bad:
            R.ok(f"{name}: {len(recs)} valid {label} record(s)")
        return recs

    cands = load("candidates.jsonl", C.validate_candidate, "candidate")
    for s in ("feeds", "youtube", "podcasts"):
        load(f"candidates/{s}.jsonl", C.validate_candidate, "candidate")
    items = load("items.jsonl", C.validate_item, "item")
    changes = load("changes.jsonl", C.validate_change, "change")
    corpus = load("corpus.jsonl", C.validate_item, "item")
    eligible = load("eligible.jsonl", C.validate_item, "item")
    excl = load("exclusions.jsonl", C.validate_exclusion, "exclusion")
    decisions = load("decisions.jsonl", C.validate_decision, "decision")
    briefs = load("briefs.jsonl", C.validate_brief, "brief")
    arts = load("articles.jsonl", C.validate_manifest, "manifest")
    scripts = load("video_scripts.jsonl", C.validate_manifest, "manifest")
    finish_section("record streams")

    # ---- duplicates and evidence assets -------------------------------------------------
    if cands is not None:
        seen, dup = {}, 0
        for c in cands:
            seen[c.get("item_id")] = seen.get(c.get("item_id"), 0) + 1
        dup = sum(v - 1 for v in seen.values() if v > 1)
        if dup:
            R.warn(f"candidates.jsonl has {dup} duplicate observation(s); they inflate raw counts and must be reported separately")
    if corpus is not None:
        ids = [c["item_id"] for c in corpus if isinstance(c, dict) and "item_id" in c]
        if len(ids) != len(set(ids)):
            R.err("corpus.jsonl has more than one record for the same item_id (store list must emit the latest version only)")
        else:
            R.ok("corpus.jsonl: one record per item_id")
    if changes is not None and items is not None and len(changes) != len(items):
        R.warn(f"changes.jsonl has {len(changes)} records for {len(items)} items; upsert emits one per input record")
    seg_cache = {}
    for name, recs in (("eligible", eligible), ("corpus", corpus)):
        for it in recs or []:
            if not isinstance(it, dict) or "text_path" not in it:
                continue
            tp = it.get("text_path")
            if not (isinstance(tp, str) and os.path.isfile(tp)):
                R.err(f"{name}: text_path does not resolve from the repo root for {it.get('item_id')}: {tp!r}")
            sp = it.get("segments_path")
            if sp:
                if not os.path.isfile(sp):
                    R.err(f"{name}: segments_path does not resolve for {it.get('item_id')}: {sp!r}")
                else:
                    try:
                        segs = read_json(sp)
                        seg_cache[sp] = {s.get("segment_id") for s in segs if isinstance(s, dict)}
                        for pr in C.validate_segments(segs, sp):
                            R.err(pr)
                    except json.JSONDecodeError:
                        R.err(f"segments file is not valid JSON: {sp}")
    finish_section("duplicates and retained assets")

    # ---- the date window -------------------------------------------------------------------
    if eligible is not None and as_of:
        start = as_of - dt.timedelta(days=window - 1)
        old30 = []
        for it in eligible:
            d0 = to_date(it.get("published_at") or "")
            if d0 is None:
                R.err(f"eligible item has no valid publication date: {it.get('item_id')}")
            elif d0 < start or d0 > as_of:
                R.err(f"eligible item outside the {window}-day window ({start}..{as_of}): {it.get('item_id')} published {d0}")
            elif (as_of - d0).days > 29:
                old30.append(it["item_id"])
        if old30:
            R.warn(f"{len(old30)} eligible item(s) are 30-44 days old (outside the assignment's 30-day rule): {old30[:6]}")
        if not R.errors:
            R.ok(f"every eligible item is inside {start}..{as_of}")
    if excl is not None:
        reasons = {}
        for e in excl:
            reasons[e.get("reason")] = reasons.get(e.get("reason"), 0) + 1
        R.ok(f"exclusions by reason: {reasons}")
    finish_section("freshness window")

    # ---- coverage minimums (README) ---------------------------------------------------------------
    elig_map = {}
    if eligible:
        elig_map = {i["item_id"]: i for i in eligible if isinstance(i, dict) and "item_id" in i}
        kinds, pubs = {}, set()
        for it in elig_map.values():
            kinds[it.get("kind")] = kinds.get(it.get("kind"), 0) + 1
            pubs.add(it.get("publisher_id"))
        (R.ok if len(elig_map) >= 12 else R.err)(f"distinct eligible items: {len(elig_map)} (need at least 12)")
        (R.ok if len(pubs) >= 6 else R.err)(f"independent publishers: {len(pubs)} (need at least 6)")
        for k in ("feed", "youtube", "podcast"):
            (R.ok if kinds.get(k, 0) >= 2 else R.err)(f"{k} items: {kinds.get(k, 0)} (need at least 2)")
        by = {}
        for it in elig_map.values():
            if it.get("kind") in ("youtube", "podcast"):
                by.setdefault((it.get("publisher_id"), norm_title(it.get("title"))), set()).add(it["kind"])
        for key, ks in by.items():
            if len(ks) > 1:
                R.warn(f"possible duplicate recording counted as two items (same publisher and title on YouTube and podcast): {key}")
    finish_section("coverage minimums (these are per run; your submission needs them across the live runs)")

    # ---- editorial decisions -------------------------------------------------------------------
    if decisions is not None and eligible is not None:
        dmap = {}
        for dcs in decisions:
            dmap.setdefault(dcs.get("item_id"), []).append(dcs)
        for iid, lst in dmap.items():
            if len(lst) > 1:
                R.err(f"item decided more than once: {iid}")
            if iid not in elig_map:
                R.err(f"decision for an item that is not eligible: {iid}")
            elif lst[0].get("version_id") != elig_map[iid].get("version_id"):
                R.err(f"decision cites a different version than the eligible record: {iid}")
        for iid in elig_map:
            if iid not in dmap:
                R.err(f"eligible item has no editorial decision: {iid}")
        counts = {k: sum(1 for x in decisions if x.get("decision") == k) for k in C.DECISIONS}
        R.ok(f"decisions: {counts}")
        if counts["reject"] + counts["defer"] < 3 or counts["accept"] < 3:
            R.warn("the README review needs at least three accepted and three rejected or deferred items")
    finish_section("editorial decisions")

    # ---- briefs, claims, evidence -----------------------------------------------------------------
    claim_ids, claim_pieces = {}, {}
    if briefs is not None:
        ids = sorted(b.get("piece_id") for b in briefs if isinstance(b, dict))
        if ids != C.PIECE_IDS:
            R.err(f"briefs.jsonl must hold exactly three briefs with piece ids 01, 02, 03; found {ids}")
        series_kinds = set()
        accepted_for = {}
        for dcs in decisions or []:
            for pid in dcs.get("piece_ids", []):
                accepted_for.setdefault(pid, set()).add(dcs.get("item_id"))
        for b in briefs:
            if not isinstance(b, dict) or not isinstance(b.get("claims"), list):
                continue
            pid = b.get("piece_id")
            pubs, has_multi_inference = set(), False
            for cl in b["claims"]:
                if not isinstance(cl, dict):
                    continue
                claim_ids[cl.get("claim_id")] = cl
                claim_pieces[cl.get("claim_id")] = pid
                cl_pubs = set()
                for ev in cl.get("evidence", []):
                    if not isinstance(ev, dict):
                        continue
                    it = elig_map.get(ev.get("item_id"))
                    if it is None:
                        R.err(f"{cl.get('claim_id')}: evidence item is not in eligible.jsonl: {ev.get('item_id')}")
                        continue
                    if it.get("version_id") != ev.get("version_id"):
                        R.err(f"{cl.get('claim_id')}: evidence cites version {ev.get('version_id')} but eligible has {it.get('version_id')}")
                    if pid in accepted_for and ev.get("item_id") not in accepted_for[pid]:
                        R.warn(f"{cl.get('claim_id')}: cites {ev.get('item_id')}, which was not accepted for piece {pid}")
                    pubs.add(it.get("publisher_id"))
                    cl_pubs.add(it.get("publisher_id"))
                    series_kinds.add(it.get("kind"))
                    loc = ev.get("locator", {})
                    if loc.get("type") == "text" and os.path.isfile(it.get("text_path", "")):
                        text = read_text(it["text_path"])
                        q = loc.get("quote", "")
                        if q and q not in text:
                            if re.sub(r"\s+", " ", q) in re.sub(r"\s+", " ", text):
                                R.warn(f"{cl.get('claim_id')}: quote matches only after whitespace normalization")
                            else:
                                R.err(f"{cl.get('claim_id')}: quote not found in the source text of {it['item_id']}: {q[:70]!r}")
                    elif loc.get("type") == "segment":
                        sp = it.get("segments_path")
                        if not sp or loc.get("segment_id") not in seg_cache.get(sp, set()):
                            R.err(f"{cl.get('claim_id')}: segment {loc.get('segment_id')!r} not found for {it['item_id']}")
                    if not a.no_store:
                        r = subprocess.run(["bash", "data/store.sh", "get", ev.get("item_id", ""), ev.get("version_id", "")],
                                           capture_output=True, text=True)
                        if r.returncode != 0:
                            R.err(f"{cl.get('claim_id')}: store.sh cannot retrieve {ev.get('item_id')} version {ev.get('version_id')}")
                if cl.get("type") == "inference" and len(cl_pubs) >= 2:
                    has_multi_inference = True
            if len(pubs) < 3:
                R.err(f"piece {pid}: evidence comes from {len(pubs)} independent publisher(s); at least 3 are required")
            else:
                R.ok(f"piece {pid}: evidence from {len(pubs)} independent publishers")
            if not has_multi_inference:
                R.warn(f"piece {pid}: no inference claim combining evidence from two or more publishers (the README asks for a connecting insight)")
        missing_kinds = {"feed", "youtube", "podcast"} - series_kinds
        if missing_kinds:
            R.err(f"the series cites no evidence from: {sorted(missing_kinds)} (all three input types must contribute)")
        else:
            R.ok("all three input types contribute evidence across the series")
        if len(claim_ids) != sum(len(b.get("claims", [])) for b in briefs if isinstance(b, dict)):
            R.err("claim_ids are not unique across briefs")
    finish_section("briefs, claims and evidence")

    # ---- articles and scripts ---------------------------------------------------------------------
    for label, man, lo, hi in (("article", arts, 600, 900), ("video script", scripts, 450, 750)):
        if man is None:
            continue
        got = sorted(m.get("piece_id") for m in man if isinstance(m, dict))
        if got != C.PIECE_IDS:
            R.err(f"{label} manifest must cover pieces 01, 02, 03; found {got}")
        for m in man:
            if not isinstance(m, dict) or not m.get("path"):
                continue
            if not os.path.isfile(m["path"]):
                R.err(f"{label} file missing: {m['path']}")
                continue
            text = read_text(m["path"])
            for cid in m.get("claim_ids", []):
                if cid not in claim_ids:
                    R.err(f"{label} {m['piece_id']}: claim {cid} is not in the briefs")
                elif cid not in text:
                    R.err(f"{label} {m['piece_id']}: marker {cid} does not appear in the draft")
            n = words(body_before_references(text)) if label == "article" else words(narration_only(text))
            if not lo <= n <= hi:
                R.warn(f"{label} {m['piece_id']}: about {n} words (target roughly {lo}-{hi})")
    if arts and scripts:
        a_ids = {m["piece_id"]: set(m.get("claim_ids", [])) for m in arts if isinstance(m, dict) and "piece_id" in m}
        s_ids = {m["piece_id"]: set(m.get("claim_ids", [])) for m in scripts if isinstance(m, dict) and "piece_id" in m}
        for pid in C.PIECE_IDS:
            if a_ids.get(pid) != s_ids.get(pid):
                R.warn(f"piece {pid}: article and video script reference different claims")
    finish_section("articles and video scripts")

    # ---- review, approval, summary, receipts ------------------------------------------------------------
    review = None
    if os.path.isfile(P("review.json")):
        review = read_json(P("review.json"))
        for k in ("review_id", "passed", "issues"):
            if k not in review:
                R.err(f"review.json missing '{k}'")
        if review.get("passed") is False:
            R.warn(f"review.json: passed is false with {len(review.get('issues', []))} issue(s)")
        errs = [i for i in review.get("issues", []) if i.get("severity") == "error"]
        if errs:
            R.warn(f"review.json has {len(errs)} error-severity issue(s)")
    else:
        R.warn("review.json not present")
    if os.path.isfile(P("approval.json")):
        ap_ = read_json(P("approval.json"))
        for k in ("review_id", "decision", "reviewer", "reviewed_at", "notes"):
            if k not in ap_:
                R.err(f"approval.json missing '{k}'")
        if ap_.get("decision") not in ("approve", "revise"):
            R.err(f"approval.json decision must be approve or revise, got {ap_.get('decision')!r}")
        if review and ap_.get("review_id") != review.get("review_id"):
            R.warn("approval.json review_id does not match review.json (stale approval)")
        if not str(ap_.get("notes", "")).strip():
            R.warn("approval.json notes is empty; record corrections and why they were needed")
    else:
        R.warn("approval.json not present (human review has not been recorded)")
    if os.path.isfile(P("summary.json")):
        s = read_json(P("summary.json"))
        if s.get("status") not in C.STATUSES:
            R.err(f"summary.json status must be one of {sorted(C.STATUSES)}, got {s.get('status')!r}")
        if s.get("run_id") != run.get("run_id"):
            R.warn("summary.json run_id differs from run.json")
    else:
        R.warn("summary.json not present")
    logs = P("logs")
    if os.path.isdir(logs):
        files = sorted(f for f in os.listdir(logs) if not f.startswith(".") and not f.endswith((".events.jsonl", ".response.txt", ".stderr.txt")))  # raw model output is kept in logs/ per BUILD_PROMPT; it is not a receipt
        if not files:
            R.err("logs/ contains no receipts")
        for f in files:
            try:
                rec = read_json(os.path.join(logs, f))
            except (json.JSONDecodeError, OSError):
                R.err(f"receipt is not valid JSON: logs/{f}")
                continue
            miss = C.receipt_missing_concepts(rec)
            if miss:
                R.warn(f"logs/{f}: receipt lacks {miss}")
        R.ok(f"{len(files)} receipt(s) in logs/")
    else:
        R.err("logs/ directory missing")
    if os.path.isdir(P("package")):
        for f in ("manifest.json", "publication_links.json"):
            (R.ok if os.path.isfile(P("package", f)) else R.err)(f"package/{f} {'present' if os.path.isfile(P('package', f)) else 'missing'}")
    finish_section("review, approval, summary, receipts, package")

    print(f"\n{TOTALS['errors']} error(s), {TOTALS['warns']} warning(s)")
    return 1 if TOTALS["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
