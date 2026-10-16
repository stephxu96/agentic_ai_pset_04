"""reporting/summarize_run.sh: it must work on incomplete runs and never claim what did not happen."""
import json
import os
import unittest

import contracts
from harness import PipelineTest, to_jsonl, ts, days_before, AS_OF


def keys_with(obj, needle):
    """All (key, value) pairs, at any depth, whose key contains `needle` (case-insensitive)."""
    out = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if needle in str(k).lower():
                    out.append((k, v))
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(obj)
    return out


class TestSummaryIncompleteRuns(PipelineTest):
    REQUIRES = ["reporting/summarize_run.sh"]

    def summarize(self, rd):
        p = self.sb.run("reporting/summarize_run.sh", [rd])
        self.assert_exit(p, 0, "summaries must work for incomplete runs")
        try:
            return json.loads(p.stdout)
        except json.JSONDecodeError:
            self.fail(f"stdout must be one JSON object{self.out(p)}")

    def count(self, summ, name):
        found, val = contracts.find_key(summ, name)
        self.assertTrue(found, f"summary should report a '{name}' count (null when the stage did not run)")
        return val

    def test_works_on_a_run_that_has_only_run_json(self):
        rd = self.sb.make_run("run-empty")
        summ = self.summarize(rd)
        self.assertEqual(summ.get("run_id"), "run-empty")
        self.assertIn(summ.get("status"), contracts.STATUSES)
        self.assertNotEqual(summ["status"], "ready_for_production", "nothing was produced, so it cannot be ready")

    def test_counts_for_stages_that_did_not_run_are_null_not_zero(self):
        summ = self.summarize(self.sb.make_run("run-empty"))
        for name in ("discovered", "extracted", "new", "changed", "unchanged", "eligible",
                     "excluded", "accepted", "rejected", "deferred"):
            self.assertIsNone(self.count(summ, name), f"'{name}' did not run, so it must be null (not 0)")

    def test_a_measured_empty_result_is_zero_not_null(self):
        rd = self.sb.make_run("run-zero")
        for name in ("eligible", "exclusions", "decisions"):
            self.sb.write(f"{rd}/{name}.jsonl", "")
        summ = self.summarize(rd)
        for name in ("eligible", "excluded", "accepted", "rejected", "deferred"):
            self.assertEqual(self.count(summ, name), 0, f"'{name}' was measured as empty, so it must be 0")

    def test_missing_run_dir_argument_is_exit_2(self):
        self.assert_exit(self.sb.run("reporting/summarize_run.sh", []), 2)

    def test_nonexistent_run_dir_is_exit_2(self):
        self.assert_exit(self.sb.run("reporting/summarize_run.sh", ["runs/does-not-exist"]), 2)

    def test_absent_costs_are_not_reported_as_zero(self):
        summ = self.summarize(self.sb.make_run("run-nocost"))
        for k, v in keys_with(summ, "cost"):
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                self.assertNotEqual(v, 0, f"'{k}' claims a zero cost although no stage reported any")


class TestSummaryFullRun(PipelineTest):
    REQUIRES = ["reporting/summarize_run.sh", "review/check_content.sh", "data/store.sh"]

    def setUp(self):
        super().setUp()
        self.rd = self.setup_or_error(self.sb.build_series_run)

    def summarize(self):
        p = self.sb.run("reporting/summarize_run.sh", [self.rd])
        self.assert_exit(p, 0)
        try:
            return json.loads(p.stdout)
        except json.JSONDecodeError:
            self.fail(f"stdout must be one JSON object{self.out(p)}")

    def val(self, summ, name):
        found, v = contracts.find_key(summ, name)
        self.assertTrue(found, f"summary should report '{name}'")
        return v

    def test_counts_match_the_run_artifacts(self):
        summ = self.summarize()
        expected = {"discovered": 15, "extracted": 15, "new": 15, "changed": 0, "unchanged": 0,
                    "eligible": 14, "excluded": 1, "accepted": 12, "rejected": 1, "deferred": 1}
        for name, want in expected.items():
            self.assertEqual(self.val(summ, name), want, f"count '{name}'")

    def test_reports_article_and_video_script_counts(self):
        summ = self.summarize()
        arts = [v for k, v in keys_with(summ, "article")]
        scripts = [v for k, v in keys_with(summ, "script")]
        self.assertIn(3, arts, "should report 3 articles")
        self.assertIn(3, scripts, "should report 3 video scripts")

    def test_reports_source_coverage_by_kind_and_publisher(self):
        text = json.dumps(self.summarize()).lower()
        for kind in ("feed", "youtube", "podcast"):
            self.assertIn(kind, text, f"coverage by kind should mention '{kind}'")
        self.assertTrue(keys_with(self.summarize(), "publisher"), "coverage should count independent publishers")

    def test_reports_elapsed_time_and_remaining_manual_actions(self):
        summ = self.summarize()
        self.assertTrue(keys_with(summ, "elapsed") or keys_with(summ, "duration"), "report elapsed time")
        self.assertTrue(keys_with(summ, "manual"), "report remaining manual actions")

    def test_duplicate_observations_are_reported_separately(self):
        cands = self.sb.read_jsonl(self.rd + "/candidates.jsonl")
        self.sb.write_jsonl(self.rd + "/candidates.jsonl", cands + [cands[0]])
        summ = self.summarize()
        dups = keys_with(summ, "duplicate")
        self.assertTrue(dups, "duplicate observations that inflate raw counts should be reported separately")
        self.assertTrue(any(isinstance(v, (int, float)) and v >= 1 for _, v in dups) or
                        any(isinstance(v, list) and v for _, v in dups))

    def test_status_is_awaiting_review_when_checked_but_not_approved(self):
        p, rev = self.sb.check(self.rd)
        self.assertIsNotNone(rev)
        self.sb.write_json(self.rd + "/review.json", rev)
        self.assertEqual(self.summarize()["status"], "awaiting_review")

    def test_a_failed_stage_receipt_is_reported_not_hidden(self):
        """Take a real receipt written by your filter, flip its status to failed, and expect the summary to change and name the stage."""
        if not self.sb.implemented("processing/filter_items.sh"):
            self.fail("processing/filter_items.sh is not implemented yet (needed to produce a real receipt)")
        self.sb.run("processing/filter_items.sh", [self.rd], stdin=to_jsonl(
            [self.sb.make_item("z", "feed", "pub-z", published=ts(days_before(AS_OF, 2)), assets=False)]))
        logs = sorted(f for f in os.listdir(self.sb.path(self.rd + "/logs")) if not f.startswith("."))
        self.assertTrue(logs, "filter_items.sh should have written a receipt")
        rec = self.sb.read_json(self.rd + "/logs/" + logs[0])
        before = self.summarize()
        flipped = False
        for k in list(rec.keys()):
            if "status" in k.lower():
                rec[k] = "failed"
                flipped = True
        self.assertTrue(flipped, "could not find a status field at the top level of your receipt")
        self.sb.write_json(self.rd + "/logs/" + logs[0], rec)
        after = self.summarize()
        self.assertNotEqual(before, after, "a receipt that says a stage failed must change the summary")
        stage = next((v for k, v in rec.items() if "stage" in k.lower() and isinstance(v, str)), None)
        if stage:
            self.assertIn(stage, json.dumps(after), "the summary should name the failed stage")


class TestSummaryReadiness(PipelineTest):
    REQUIRES = ["reporting/summarize_run.sh", "review/check_content.sh", "publishing/prepare_package.sh",
                "data/store.sh"]

    def test_status_is_ready_for_production_after_approval_and_packaging(self):
        rd = self.setup_or_error(self.sb.build_series_run)
        p, rev = self.sb.check(rd)
        self.assertIsNotNone(rev)
        self.sb.write_json(rd + "/review.json", rev)
        self.sb.approve(rd, rev["review_id"])
        self.assert_exit(self.sb.run("publishing/prepare_package.sh", [rd]), 0)
        p = self.sb.run("reporting/summarize_run.sh", [rd])
        self.assert_exit(p, 0)
        self.assertEqual(json.loads(p.stdout)["status"], "ready_for_production")


if __name__ == "__main__":
    unittest.main()
