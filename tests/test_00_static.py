"""Structure and configuration checks (no network, no AI)."""
import json
import os
import re
import unittest

import contracts
from harness import PipelineTest, REQUIRED_SCRIPTS, is_implemented, read_file


class TestRepositoryStructure(PipelineTest):
    def test_all_16_required_scripts_exist(self):
        missing = [s for s in REQUIRED_SCRIPTS if not os.path.isfile(self.sb.path(s))]
        self.assertFalse(missing, f"missing required scripts: {missing}")

    def test_required_scripts_are_implemented(self):
        empty = [s for s in REQUIRED_SCRIPTS if not is_implemented(self.sb.path(s))]
        self.assertFalse(empty, f"still empty (an empty Bash file exits 0 and does nothing): {empty}")

    def test_scripts_have_bash_shebang(self):
        bad = []
        for s in REQUIRED_SCRIPTS:
            p = self.sb.path(s)
            if is_implemented(p):
                first = read_file(p).splitlines()[0]
                if not re.match(r"#!.*\bbash\b", first):
                    bad.append(s)
        self.assertFalse(bad, f"missing a Bash shebang on line 1: {bad}")

    def test_scripts_pass_bash_syntax_check(self):
        import subprocess
        bad = []
        for s in REQUIRED_SCRIPTS:
            if is_implemented(self.sb.path(s)):
                r = subprocess.run(["bash", "-n", self.sb.path(s)], capture_output=True, text=True)
                if r.returncode != 0:
                    bad.append(f"{s}: {r.stderr.strip()[:150]}")
        self.assertFalse(bad, "\n".join(bad))

    def test_only_store_sh_touches_the_evidence_index(self):
        """ARCHITECTURE.md: only data/store.sh may read or write data/evidence/."""
        offenders = []
        skip_dirs = {".git", "tests", "runs", "examples", "node_modules", "__pycache__"}
        skip_files = {"README.md", "ARCHITECTURE.md", "SUBMISSION.md"}
        for dirpath, dirnames, filenames in os.walk(self.sb.root):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]
            rel_dir = os.path.relpath(dirpath, self.sb.root)
            for fn in filenames:
                rel = os.path.normpath(os.path.join(rel_dir, fn))
                if rel == os.path.join("data", "store.sh") or fn in skip_files:
                    continue
                if rel.startswith(os.path.join("data", "store")):  # helpers owned by the store
                    continue
                try:
                    text = read_file(os.path.join(dirpath, fn))
                except (UnicodeDecodeError, OSError):
                    continue
                if "data/evidence" in text:
                    offenders.append(rel)
        self.assertFalse(offenders,
                         "these files mention data/evidence; only data/store.sh (and helpers named data/store*) "
                         f"may touch it: {offenders}")

    def test_no_obvious_credentials_in_repo(self):
        patterns = [r"sk-[A-Za-z0-9]{20,}", r"AKIA[0-9A-Z]{16}", r"ghp_[A-Za-z0-9]{30,}",
                    r"(?i)(api[_-]?key|secret|token)\s*[=:]\s*['\"][A-Za-z0-9_\-]{16,}['\"]"]
        hits = []
        for dirpath, dirnames, filenames in os.walk(self.sb.root):
            # Installed dependencies are not repository source and may contain
            # credential-shaped examples or extractor signatures.
            dirnames[:] = [d for d in dirnames if d not in {".git", ".venv", "venv", "node_modules", "__pycache__"}]
            for fn in filenames:
                p = os.path.join(dirpath, fn)
                try:
                    text = read_file(p)
                except (UnicodeDecodeError, OSError):
                    continue
                for pat in patterns:
                    if re.search(pat, text):
                        hits.append(os.path.relpath(p, self.sb.root))
                        break
        self.assertFalse(hits, f"possible credentials committed (use environment variables): {hits}")


class TestConfiguration(PipelineTest):
    def test_project_json_has_four_nonempty_strings(self):
        try:
            cfg = self.sb.read_json("config/project.json")
        except (OSError, json.JSONDecodeError) as e:
            self.fail(f"config/project.json missing or invalid JSON: {e}")
        for k in ("publication_name", "topic", "audience", "central_question"):
            self.assertTrue(contracts.nonempty_str(cfg.get(k)), f"project.json '{k}' must be a nonempty string")

    def test_freshness_window_setting_is_a_positive_integer_when_present(self):
        cfg = self.sb.read_json("config/project.json")
        if "freshness_window_days" in cfg:
            v = cfg["freshness_window_days"]
            self.assertTrue(isinstance(v, int) and not isinstance(v, bool) and v > 0,
                            f"freshness_window_days must be a positive integer, got {v!r}")

    def test_sources_json_shape(self):
        try:
            src = self.sb.read_json("config/sources.json")
        except (OSError, json.JSONDecodeError) as e:
            self.fail(f"config/sources.json missing or invalid JSON: {e}")
        self.assertIsInstance(src, list, "sources.json must be an array")
        self.assertTrue(src, "sources.json is empty")
        ids = set()
        for i, s in enumerate(src):
            for k in ("source_id", "publisher_id", "kind", "url"):
                self.assertTrue(contracts.nonempty_str(s.get(k)), f"sources[{i}] needs a nonempty '{k}'")
            self.assertIn(s["kind"], contracts.KINDS, f"sources[{i}] kind must be one of {sorted(contracts.KINDS)}")
            self.assertNotIn(s["source_id"], ids, f"duplicate source_id {s['source_id']}")
            ids.add(s["source_id"])

    def test_sources_cover_all_three_kinds_and_six_publishers(self):
        src = self.sb.read_json("config/sources.json")
        kinds = {s.get("kind") for s in src}
        self.assertEqual(kinds & contracts.KINDS, contracts.KINDS, f"need feed, youtube and podcast sources; have {sorted(kinds)}")
        pubs = {s.get("publisher_id") for s in src}
        self.assertGreaterEqual(len(pubs), 6, f"README needs six independent sources; only {len(pubs)} distinct publisher_ids")

    def test_editorial_policy_covers_required_topics(self):
        text = self.sb.read("config/editorial_policy.md").lower()
        self.assertTrue(text.strip(), "config/editorial_policy.md is empty")
        missing = [t for t in ("relevance", "freshness", "credibility", "novelty", "perspective",
                               "uncertainty", "exclusion") if t not in text]
        self.assertFalse(missing, f"editorial policy does not mention: {missing}")

    def test_prompts_exist_and_are_nonempty(self):
        for name in ("select_items", "create_briefs", "write_articles", "write_video_scripts"):
            p = f"prompts/{name}.md"
            self.assertTrue(self.sb.exists(p), f"{p} missing")
            self.assertTrue(self.sb.read(p).strip(), f"{p} is empty")


if __name__ == "__main__":
    unittest.main()
