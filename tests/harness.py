"""Test harness for the MIT 1.125 PS4 intelligence pipeline.

Runs your Bash components in a throwaway copy of the repo, so tests never touch
your real data/evidence, data/assets, or runs/. Python 3 standard library only.
"""
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import contracts  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("REPO_ROOT") or os.path.dirname(HERE)

REQUIRED_SCRIPTS = [
    "run.sh",
    "workflows/collect_sources.sh",
    "workflows/create_series.sh",
    "collectors/fetch_feeds.sh",
    "collectors/fetch_youtube.sh",
    "collectors/fetch_podcasts.sh",
    "processing/extract_content.sh",
    "processing/filter_items.sh",
    "data/store.sh",
    "editorial/select_items.sh",
    "editorial/create_briefs.sh",
    "content/write_articles.sh",
    "content/write_video_scripts.sh",
    "review/check_content.sh",
    "publishing/prepare_package.sh",
    "reporting/summarize_run.sh",
]

AS_OF = "2026-10-15"  # fixed as-of date for deterministic fixtures
DEFAULT_PROJECT = {
    "publication_name": "Test Publication",
    "topic": "A test topic.",
    "audience": "A test audience.",
    "central_question": "A test question?",
    "freshness_window_days": 30,
}


_DEFAULT = object()


class SetupError(Exception):
    """A fixture could not be built (usually because a prerequisite component is broken)."""


def read_file(path, mode="r"):
    with open(path, mode, **({} if "b" in mode else {"encoding": "utf-8", "errors": "replace"})) as fh:
        return fh.read()


def is_implemented(path):
    """False when the file is missing, empty, or only a shebang/comments."""
    if not os.path.isfile(path):
        return False
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if s and not s.startswith("#"):
                return True
    return False


def parse_jsonl(text, where="output"):
    recs = []
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            recs.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise AssertionError(f"{where} line {n} is not valid JSON ({e}): {line[:120]!r}")
    return recs


def to_jsonl(recs):
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs)


def d(s):
    return dt.date.fromisoformat(s)


def ts(date, hour=12, minute=0, second=0):
    if isinstance(date, str):
        date = d(date)
    return f"{date.isoformat()}T{hour:02d}:{minute:02d}:{second:02d}Z"


def days_before(as_of, n):
    return d(as_of) - dt.timedelta(days=n)


def sha(*parts):
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:16]


def safe(s):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in s)


class Sandbox:
    """A temporary copy of the repo where components run with cwd = repo root."""

    def __init__(self, repo=REPO):
        self.repo = repo
        self.tmp = tempfile.mkdtemp(prefix="pipeline-test-")
        self.root = os.path.join(self.tmp, "repo")

        def ignore(dirpath, names):
            rel = os.path.relpath(dirpath, repo)
            out = set()
            for n in names:
                p = os.path.normpath(os.path.join(rel, n))
                if n in (".git", ".venv", "venv", "__pycache__", "node_modules", ".DS_Store"):
                    out.add(n)
                elif p in ("runs", "tests", "data/evidence", "data/media", "data/assets"):
                    out.add(n)
            return out

        shutil.copytree(repo, self.root, ignore=ignore)

    def cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- paths and files -------------------------------------------------
    def path(self, rel):
        return os.path.join(self.root, rel)

    def implemented(self, rel):
        return is_implemented(self.path(rel))

    def write(self, rel, content):
        p = self.path(rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)

    def read(self, rel):
        with open(self.path(rel), encoding="utf-8") as f:
            return f.read()

    def exists(self, rel):
        return os.path.exists(self.path(rel))

    def read_json(self, rel):
        return json.loads(self.read(rel))

    def read_jsonl(self, rel):
        return parse_jsonl(self.read(rel), rel)

    def write_json(self, rel, obj):
        self.write(rel, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")

    def write_jsonl(self, rel, recs):
        self.write(rel, to_jsonl(recs))

    # -- running components ---------------------------------------------
    def run(self, script, args=(), stdin="", env=None, timeout=120):
        e = dict(os.environ)
        e.update(env or {})
        return subprocess.run(
            ["bash", script, *args], cwd=self.root, input=stdin,
            capture_output=True, text=True, timeout=timeout, env=e,
        )

    def store(self, *args, stdin=""):
        return self.run("data/store.sh", args, stdin=stdin)

    # -- state resets ----------------------------------------------------
    def reset_store(self):
        shutil.rmtree(self.path("data/evidence"), ignore_errors=True)

    def reset_runs(self):
        shutil.rmtree(self.path("runs"), ignore_errors=True)
        os.makedirs(self.path("runs"), exist_ok=True)

    # -- fixtures ---------------------------------------------------------
    def make_run(self, run_id="run-1", as_of=AS_OF, mode="live", window=30,
                 previous=None, project_overrides=None):
        """Create runs/RUN_ID with run.json, config/ and prompts/ snapshots. Returns 'runs/RUN_ID'."""
        rd = f"runs/{run_id}"
        os.makedirs(self.path(rd + "/logs"), exist_ok=True)
        self.write_json(rd + "/run.json", {
            "run_id": run_id, "started_at": f"{as_of}T09:00:00Z", "as_of_date": as_of,
            "mode": mode, "previous_run_id": previous,
        })
        # config snapshot: use the repo's config where valid, else defaults
        project = dict(DEFAULT_PROJECT)
        try:
            with open(self.path("config/project.json"), encoding="utf-8") as fh:
                real = json.loads(fh.read())
            if all(contracts.nonempty_str(real.get(k)) for k in
                   ("publication_name", "topic", "audience", "central_question")):
                project = real
        except (OSError, json.JSONDecodeError):
            pass
        project["freshness_window_days"] = window
        project.update(project_overrides or {})
        self.write_json(rd + "/config/project.json", project)
        for name in ("sources.json", "editorial_policy.md"):
            src = self.path("config/" + name)
            if os.path.isfile(src) and os.path.getsize(src) > 0:
                shutil.copy(src, self.path(f"{rd}/config/{name}"))
        if not self.exists(rd + "/config/sources.json"):
            self.write_json(rd + "/config/sources.json", [
                {"source_id": "s1", "publisher_id": "pub-a", "kind": "feed", "url": "https://example.test/feed"}])
        if not self.exists(rd + "/config/editorial_policy.md"):
            self.write(rd + "/config/editorial_policy.md", "# Policy\nTest policy.\n")
        if os.path.isdir(self.path("prompts")):
            shutil.copytree(self.path("prompts"), self.path(rd + "/prompts"), dirs_exist_ok=True)
        os.makedirs(self.path(rd + "/prompts"), exist_ok=True)
        return rd

    def write_assets(self, item_id, version_id, text, segments=None):
        base = f"data/assets/{safe(item_id)}"
        tp = f"{base}/{version_id}.txt"
        self.write(tp, text)
        sp = None
        if segments is not None:
            sp = f"{base}/{version_id}.segments.json"
            self.write_json(sp, segments)
        return tp, sp

    def make_item(self, key, kind="feed", publisher="pub-a", published=_DEFAULT, text=None,
                  version=None, title=None, retrieved=None, assets=True):
        prefix = {"feed": "feed:", "youtube": "youtube:", "podcast": "podcast:"}[kind]
        item_id = prefix + key
        title = title or f"Item {key} title"
        if published is _DEFAULT:
            published = ts(days_before(AS_OF, 5))
        text = text or f"Report {key}: the model completed 17 of 20 trials under the stated conditions."
        version = version or sha(text, title, published)
        retrieved = retrieved or f"{AS_OF}T09:30:00Z"
        segments = None
        if kind != "feed":
            segments = [
                {"segment_id": "s1", "start_seconds": 0.0, "end_seconds": 12.5, "text": text},
                {"segment_id": "s2", "start_seconds": 12.5, "end_seconds": 30.0,
                 "text": f"The host asks about {key} and the guest answers with caveats."},
                {"segment_id": "s3", "start_seconds": 30.0, "end_seconds": 45.0,
                 "text": f"They close the discussion of {key}."},
            ]
        tp, sp = (None, None)
        if assets:
            tp, sp = self.write_assets(item_id, version, text, segments)
        else:
            tp = f"data/assets/{safe(item_id)}/{version}.txt"
            sp = f"data/assets/{safe(item_id)}/{version}.segments.json" if kind != "feed" else None
        return {
            "item_id": item_id, "source_id": f"src-{publisher}", "publisher_id": publisher,
            "kind": kind, "title": title, "url": f"https://example.test/{kind}/{key}",
            "published_at": published, "retrieved_at": retrieved,
            "media_url": None if kind == "feed" else f"https://example.test/media/{key}.mp3",
            "version_id": version, "text_path": tp, "segments_path": sp,
        }

    def upsert(self, run_dir, items):
        p = self.store("upsert", run_dir, stdin=to_jsonl(items))
        if p.returncode != 0:
            raise SetupError(f"data/store.sh upsert failed (exit {p.returncode}): {p.stderr[:300]}")
        return p

    # -- a complete, consistent series run -------------------------------
    def build_series_run(self, run_id="run-series", as_of=AS_OF, window=30):
        """Build a valid run: 15 corpus items, 14 eligible, 1 excluded, 3 briefs,
        3 articles and 3 video scripts, with evidence stored via data/store.sh."""
        rd = self.make_run(run_id, as_of, window=window)
        spec = [
            ("a1", "feed", "pub-a"), ("a2", "feed", "pub-b"), ("a3", "feed", "pub-c"),
            ("a4", "feed", "pub-d"), ("a5", "feed", "pub-e"),
            ("y1", "youtube", "pub-f"), ("y2", "youtube", "pub-g"), ("y3", "youtube", "pub-h"),
            ("p1", "podcast", "pub-i"), ("p2", "podcast", "pub-j"), ("p3", "podcast", "pub-k"),
            ("p4", "podcast", "pub-a"), ("r1", "feed", "pub-l"), ("d1", "feed", "pub-m"),
        ]
        items = {}
        for i, (key, kind, pub) in enumerate(spec):
            items[key] = self.make_item(key, kind, pub, published=ts(days_before(as_of, 2 + i)))
        old = self.make_item("e1", "feed", "pub-n", published=ts(days_before(as_of, 70)))
        everything = list(items.values()) + [old]
        self.upsert(rd, everything)

        cands = [{k: v for k, v in it.items() if k in contracts.CANDIDATE_FIELDS} for it in everything]
        self.write_jsonl(rd + "/candidates.jsonl", cands)
        for kind, name in (("feed", "feeds"), ("youtube", "youtube"), ("podcast", "podcasts")):
            self.write_jsonl(f"{rd}/candidates/{name}.jsonl", [c for c in cands if c["kind"] == kind])
        self.write_jsonl(rd + "/items.jsonl", everything)
        self.write_jsonl(rd + "/changes.jsonl", [
            {"item_id": i["item_id"], "version_id": i["version_id"], "change": "new"} for i in everything])
        self.write_jsonl(rd + "/corpus.jsonl", everything)
        eligible = list(items.values())
        self.write_jsonl(rd + "/eligible.jsonl", eligible)
        self.write_jsonl(rd + "/exclusions.jsonl", [{
            "item_id": old["item_id"], "version_id": old["version_id"],
            "reason": "outside_window", "detail": f"published {old['published_at']}, before window start"}])

        pieces = {
            "01": ["a1", "y1", "p1", "a2"],
            "02": ["a3", "y2", "p2", "a4"],
            "03": ["a5", "y3", "p3", "a1"],
        }
        decisions = []
        for key, it in items.items():
            pids = [pid for pid, ks in pieces.items() if key in ks]
            if key == "r1":
                decisions.append(self._decision(it, "reject", "Off-topic for this audience.", []))
            elif key == "d1":
                decisions.append(self._decision(it, "defer", "Promising but no checkable passage yet.", []))
            else:
                decisions.append(self._decision(it, "accept", "Relevant, fresh, checkable.", pids or ["03"]))
        self.write_jsonl(rd + "/decisions.jsonl", decisions)

        quote = "completed 17 of 20 trials under the stated conditions"
        briefs, art_manifest, vid_manifest = [], [], []
        for pid, keys in pieces.items():
            a, b, c, e = (items[k] for k in keys)
            claims = [
                {"claim_id": f"{pid}-c1", "statement": f"Source {keys[0]} reports 17 of 20 trials completed.",
                 "type": "reported_fact", "evidence": [self._text_ref(a, quote)]},
                {"claim_id": f"{pid}-c2", "statement": f"The speaker in {keys[1]} claims results hold under stated conditions.",
                 "type": "source_claim", "evidence": [self._seg_ref(b, "s1")]},
                {"claim_id": f"{pid}-c3", "statement": "Three independent sources describe the same constraint.",
                 "type": "inference",
                 "evidence": [self._text_ref(e, quote), self._seg_ref(c, "s2"), self._text_ref(a, quote)]},
            ]
            briefs.append({
                "piece_id": pid, "title": f"Piece {pid} title",
                "question": f"Editorial question for piece {pid}?",
                "argument": f"Distinct argument number {pid}.",
                "synthesis": f"Connecting the sources shows constraint {pid}.",
                "limitations": f"Limitation {pid}: small sample.", "claims": claims})
            body = f"# Piece {pid} title\n\nAs of {as_of}.\n\n"
            for cl in claims:
                body += f"{cl['statement']} [{cl['claim_id']}]\n\n"
            body += "## References\n\n"
            for cl in claims:
                for ev in cl["evidence"]:
                    it = next(v for v in everything if v["item_id"] == ev["item_id"])
                    stamp = " at 00:00:00" if ev["locator"]["type"] == "segment" else ""
                    body += f"[{cl['claim_id']}] {it['title']}, {it['publisher_id']}, {it['published_at'][:10]}, {it['url']}{stamp}\n"
            self.write(f"{rd}/articles/{pid}.md", body)
            self.write(f"{rd}/video_scripts/{pid}.md",
                       f"# Script {pid}\n\n" + "".join(
                           f"Narration: {cl['statement']} ({cl['claim_id']})\nVisual: source card\n\n" for cl in claims))
            ids = [cl["claim_id"] for cl in claims]
            art_manifest.append({"piece_id": pid, "path": f"{rd}/articles/{pid}.md", "claim_ids": ids})
            vid_manifest.append({"piece_id": pid, "path": f"{rd}/video_scripts/{pid}.md", "claim_ids": ids})
        self.write_jsonl(rd + "/briefs.jsonl", briefs)
        self.write_jsonl(rd + "/articles.jsonl", art_manifest)
        self.write_jsonl(rd + "/video_scripts.jsonl", vid_manifest)
        return rd

    @staticmethod
    def _decision(it, decision, reason, pids):
        return {"item_id": it["item_id"], "version_id": it["version_id"],
                "decision": decision, "reason": reason, "piece_ids": pids}

    @staticmethod
    def _text_ref(it, quote):
        return {"item_id": it["item_id"], "version_id": it["version_id"],
                "locator": {"type": "text", "quote": quote}}

    @staticmethod
    def _seg_ref(it, seg):
        return {"item_id": it["item_id"], "version_id": it["version_id"],
                "locator": {"type": "segment", "segment_id": seg}}

    def check(self, rd):
        """Run review/check_content.sh and return (process, parsed JSON or None)."""
        p = self.run("review/check_content.sh", [rd])
        try:
            return p, json.loads(p.stdout)
        except json.JSONDecodeError:
            return p, None

    def approve(self, rd, review_id, decision="approve", **extra):
        rec = {"review_id": review_id, "decision": decision, "reviewer": "Test Reviewer",
               "reviewed_at": f"{AS_OF}T18:00:00Z", "notes": "Reviewed in test."}
        rec.update(extra)
        self.write_json(rd + "/approval.json", rec)


class PipelineTest(unittest.TestCase):
    """Base class: sandbox per class, clean store and runs per test, fail clearly when unimplemented."""

    REQUIRES = []

    @classmethod
    def setUpClass(cls):
        cls.sb = Sandbox()

    @classmethod
    def tearDownClass(cls):
        cls.sb.cleanup()

    def setUp(self):
        for rel in self.REQUIRES:
            if not self.sb.implemented(rel):
                self.fail(f"{rel} is not implemented yet (missing, empty, or comments only)")
        self.sb.reset_store()
        self.sb.reset_runs()

    # -- assertion helpers ------------------------------------------------
    def out(self, p):
        return f"\n--- exit {p.returncode}\n--- stdout:\n{p.stdout[-600:]}\n--- stderr:\n{p.stderr[-600:]}"

    def assert_exit(self, p, code, why=""):
        self.assertEqual(p.returncode, code, f"expected exit {code}{' (' + why + ')' if why else ''}{self.out(p)}")

    def jsonl(self, p):
        return parse_jsonl(p.stdout, "stdout")

    def assert_valid(self, validator, recs, name):
        problems = []
        for i, r in enumerate(recs):
            problems += validator(r, f"{name}[{i}]")
        self.assertFalse(problems, "\n".join(problems[:8]))

    def setup_or_error(self, fn, *a, **kw):
        try:
            return fn(*a, **kw)
        except SetupError as e:
            self.fail(f"fixture setup failed, so this test could not run: {e}")
