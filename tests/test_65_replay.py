"""run.sh --replay: labeled replay from stored evidence at a past as-of date. No network, no model calls."""
import glob
import json
import os
import shutil
import unittest

from harness import PipelineTest, parse_jsonl


class TestReplayMode(PipelineTest):
    REQUIRES = ["run.sh", "data/store.sh", "processing/filter_items.sh", "reporting/summarize_run.sh"]

    def setUp(self):
        super().setUp()
        shutil.copytree(os.path.join(self.sb.repo, "config"), self.sb.path("config"), dirs_exist_ok=True)
        seed = self.sb.make_run("seed-run", as_of="2026-10-15")
        items = [
            self.sb.make_item("inside", published="2026-09-28T12:00:00Z"),
            self.sb.make_item("future", published="2026-10-05T12:00:00Z", publisher="pub-b"),
            self.sb.make_item("old", published="2026-08-01T12:00:00Z", publisher="pub-c"),
            self.sb.make_item("undated", published=None, publisher="pub-d"),
        ]
        self.setup_or_error(self.sb.upsert, seed, items)

    def replay(self, *args):
        return self.sb.run("run.sh", ["--replay", *args], timeout=90)

    def newest_run(self):
        runs = sorted(glob.glob(self.sb.path("runs/*/run.json")), key=os.path.getmtime)
        runs = [r for r in runs if "seed-run" not in r]
        self.assertTrue(runs, "replay did not create a run directory")
        return os.path.dirname(runs[-1])

    def read_jsonl_file(self, path):
        with open(path, encoding="utf-8") as f:
            return parse_jsonl(f.read(), path)

    def test_replay_is_labeled_and_uses_the_given_as_of_date(self):
        p = self.replay("--as-of", "2026-10-01")
        self.assert_exit(p, 0)
        rd = self.newest_run()
        run = json.load(open(os.path.join(rd, "run.json")))
        self.assertEqual(run["mode"], "replay")
        self.assertEqual(run["as_of_date"], "2026-10-01")
        self.assertIn("replay", run["replay_note"].lower())
        self.assertNotEqual(run["started_at"][:10], "2026-10-01", "started_at must be the real execution time")

    def test_future_old_and_undated_items_are_excluded_with_reasons(self):
        self.assert_exit(self.replay("--as-of", "2026-10-01"), 0)
        rd = self.newest_run()
        eligible = {r["item_id"] for r in self.read_jsonl_file(os.path.join(rd, "eligible.jsonl"))}
        reasons = {r["item_id"]: r["reason"] for r in self.read_jsonl_file(os.path.join(rd, "exclusions.jsonl"))}
        self.assertEqual(eligible, {"feed:inside"})
        self.assertEqual(reasons, {"feed:future": "future_date", "feed:old": "outside_window",
                                   "feed:undated": "unknown_date"})

    def test_replay_does_not_collect_or_call_models_by_default(self):
        self.assert_exit(self.replay("--as-of", "2026-10-01"), 0)
        rd = self.newest_run()
        for name in ("candidates.jsonl", "items.jsonl", "changes.jsonl", "decisions.jsonl", "briefs.jsonl"):
            self.assertFalse(os.path.exists(os.path.join(rd, name)), name + " should not exist after a replay through eligible")

    def test_summary_reports_replay_without_calling_it_failed_or_publishable(self):
        self.assert_exit(self.replay("--as-of", "2026-10-01"), 0)
        rd = self.newest_run()
        summary = json.load(open(os.path.join(rd, "summary.json")))
        self.assertEqual(summary["mode"], "replay")
        self.assertNotEqual(summary["status"], "failed")
        self.assertNotEqual(summary["status"], "ready_for_production")
        self.assertEqual(summary["counts"]["eligible"], 1)
        self.assertIsNone(summary["counts"]["articles"])
        self.assertIn("replay", " ".join(summary["remaining_manual_actions"]).lower())

    def test_replaying_twice_creates_two_runs_and_no_duplicate_evidence(self):
        before = self.sb.store("list")
        self.assert_exit(self.replay("--as-of", "2026-10-01"), 0)
        self.assert_exit(self.replay("--as-of", "2026-10-12"), 0)
        after = self.sb.store("list")
        self.assertEqual(before.stdout, after.stdout, "replays must not change the evidence store")
        replay_runs = [r for r in glob.glob(self.sb.path("runs/*/run.json")) if "seed-run" not in r]
        self.assertEqual(len(replay_runs), 2)

    def test_bad_arguments_exit_2(self):
        for args in ([], ["--as-of"], ["--as-of", "not-a-date"], ["--as-of", "2099-01-01"],
                     ["--as-of", "2026-10-01", "--through", "articles"], ["--as-of", "2026-10-01", "--bogus"]):
            with self.subTest(args=args):
                self.assert_exit(self.replay(*args), 2)


if __name__ == "__main__":
    unittest.main()
