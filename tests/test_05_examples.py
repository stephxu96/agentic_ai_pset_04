"""Conformance with the starter's examples/ folder: the course's own deterministic component checks.

examples/README.md describes four checks (store ingest, store replay, date filter, brief references). The first
group below checks that this harness's record contracts agree with the starter's example files. The remaining
groups run those checks against YOUR data/store.sh and processing/filter_items.sh.
"""
import json
import os
import unittest

import contracts
from harness import PipelineTest, to_jsonl, parse_jsonl


class ExamplesCase(PipelineTest):
    def setUp(self):
        super().setUp()
        if not self.sb.exists("examples/items.jsonl"):
            self.fail("examples/items.jsonl not found: run these tests from a repo that contains the starter's examples/")

    def ex(self, name):
        return self.sb.read("examples/" + name)

    def exj(self, name):
        return self.sb.read_json("examples/" + name)

    def exl(self, name):
        return self.sb.read_jsonl("examples/" + name)


class TestExampleFilesMatchTheContracts(ExamplesCase):
    """No implementation needed: the harness's validators must accept the starter's own examples."""

    def test_sources(self):
        for i, s in enumerate(self.exj("sources.json")):
            for k in ("source_id", "publisher_id", "kind", "url"):
                self.assertTrue(contracts.nonempty_str(s.get(k)), f"sources[{i}].{k}")
            self.assertIn(s["kind"], contracts.KINDS)

    def test_candidates_items_and_ids(self):
        self.assert_valid(contracts.validate_candidate, self.exl("candidates.jsonl"), "candidate")
        items = self.exl("items.jsonl")
        self.assert_valid(contracts.validate_item, items, "item")
        for it in items:
            self.assertTrue(it["item_id"].startswith(it["kind"] + ":"),
                            f"the starter's item_id convention is '<kind>:<name>', got {it['item_id']}")

    def test_replay_and_filter_inputs_are_items(self):
        self.assert_valid(contracts.validate_item, self.exl("replay_items.jsonl"), "replay item")
        recs = []
        for line in self.ex("filter_input.jsonl").splitlines():
            recs.append(json.loads(line))
        problems = []
        for i, r in enumerate(recs):
            # the filter input deliberately contains null and malformed dates
            problems += [p for p in contracts.validate_item(r, f"filter_input[{i}]")
                         if "published_at" not in p]
        self.assertFalse(problems, "\n".join(problems[:6]))

    def test_expected_change_records(self):
        self.assert_valid(contracts.validate_change, self.exl("initial_changes_expected.jsonl"), "initial change")
        self.assert_valid(contracts.validate_change, self.exl("replay_changes_expected.jsonl"), "replay change")

    def test_decisions_briefs_manifests(self):
        self.assert_valid(contracts.validate_decision, self.exl("decisions.jsonl"), "decision")
        self.assert_valid(contracts.validate_brief, self.exl("briefs.jsonl"), "brief")
        self.assert_valid(contracts.validate_manifest, self.exl("articles.jsonl"), "article manifest")
        self.assert_valid(contracts.validate_manifest, self.exl("video_scripts.jsonl"), "script manifest")

    def test_segments(self):
        for name in ("video", "podcast", "podcast-v2"):
            self.assertFalse(contracts.validate_segments(self.exj(f"segments/{name}.json"), name))

    def test_review_approval_and_links_shapes(self):
        review = self.exj("review.json")
        for k in ("review_id", "passed", "issues"):
            self.assertIn(k, review)
        self.assertIn("severity", review["issues"][0])
        approval = self.exj("approval.json")
        for k in ("review_id", "decision", "reviewer", "reviewed_at", "notes"):
            self.assertIn(k, approval)
        links = self.exj("publication_links.json")
        self.assertEqual([r["piece_id"] for r in links], ["01", "02", "03"])
        self.assertTrue(all(r["substack_url"] is None and r["youtube_url"] is None for r in links))
        self.assertTrue(contracts.is_iso_utc(self.exj("run.json")["started_at"]))

    def test_example_brief_references_resolve(self):
        """examples/README.md check 4: every quote or segment resolves to the stated item version and file."""
        items = {(i["item_id"], i["version_id"]): i for i in self.exl("items.jsonl")}
        for brief in self.exl("briefs.jsonl"):
            for cl in brief["claims"]:
                for ev in cl["evidence"]:
                    it = items.get((ev["item_id"], ev["version_id"]))
                    self.assertIsNotNone(it, f"{cl['claim_id']}: no such item version")
                    loc = ev["locator"]
                    if loc["type"] == "text":
                        self.assertIn(loc["quote"], self.sb.read(it["text_path"]))
                    else:
                        segs = self.sb.read_json(it["segments_path"])
                        self.assertIn(loc["segment_id"], {s["segment_id"] for s in segs})


class TestStoreAgainstExamples(ExamplesCase):
    """examples/README.md checks 1 and 2, run against your data/store.sh."""
    REQUIRES = ["data/store.sh"]

    def setUp(self):
        super().setUp()
        self.rd = self.sb.make_run("example-2026-10-08", as_of="2026-10-08", mode="example")

    def ingest(self, name):
        p = self.sb.store("upsert", self.rd, stdin=self.ex(name))
        self.assert_exit(p, 0)
        return self.jsonl(p)

    def test_check_1_initial_ingest_is_three_new_items_in_order(self):
        self.assert_exit(self.sb.store("init"), 0)
        got = self.ingest("items.jsonl")
        self.assertEqual(got, self.exl("initial_changes_expected.jsonl"))

    def test_check_2_replay_is_four_unchanged_then_one_changed(self):
        self.assert_exit(self.sb.store("init"), 0)
        self.ingest("items.jsonl")
        got = self.ingest("replay_items.jsonl")
        want = self.exl("replay_changes_expected.jsonl")
        self.assertEqual(got, want, "four unchanged (including the duplicate and refreshed retrieval times), then one changed")

    def test_check_2_store_keeps_three_logical_items_and_both_podcast_versions(self):
        self.assert_exit(self.sb.store("init"), 0)
        self.ingest("items.jsonl")
        self.ingest("replay_items.jsonl")
        listed = self.jsonl(self.sb.store("list"))
        self.assertEqual(sorted(r["item_id"] for r in listed),
                         ["feed:fictional-trial", "podcast:fictional-episode", "youtube:fictional-demo"])
        v1 = self.exl("initial_changes_expected.jsonl")[2]["version_id"]
        v2 = self.exl("replay_changes_expected.jsonl")[4]["version_id"]
        podcast = next(r for r in listed if r["item_id"] == "podcast:fictional-episode")
        self.assertEqual(podcast["version_id"], v2, "list returns the latest version")
        old = self.jsonl(self.sb.store("get", "podcast:fictional-episode", v1))
        self.assertEqual(old[0]["version_id"], v1, "the first version must remain retrievable")
        self.assertEqual(old[0]["text_path"], "examples/text/podcast.txt")


class TestFilterAgainstExamples(ExamplesCase):
    """examples/README.md check 3, run against your processing/filter_items.sh."""
    REQUIRES = ["processing/filter_items.sh"]

    def test_check_3_filter_matches_filter_expected(self):
        run = self.exj("run.json")
        rd = self.sb.make_run(run["run_id"], as_of=run["as_of_date"], mode=run["mode"], window=30)
        self.sb.write_json(rd + "/run.json", run)  # the example's own run metadata
        p = self.sb.run("processing/filter_items.sh", [rd], stdin=self.ex("filter_input.jsonl"))
        self.assert_exit(p, 0, "the deliberately malformed date must be excluded, not crash the filter")
        want = self.exj("filter_expected.json")
        eligible = [r["item_id"] for r in self.jsonl(p)]
        self.assertEqual(sorted(eligible), sorted(want["eligible_item_ids"]), "eligible IDs (order ignored)")
        excl = self.sb.read_jsonl(rd + "/exclusions.jsonl")
        got = sorted((e["item_id"], e["reason"]) for e in excl)
        self.assertEqual(got, sorted((e["item_id"], e["reason"]) for e in want["exclusions"]))
        self.assertEqual(want["window_start"], "2026-09-09")
        self.assertEqual(want["window_end"], "2026-10-08")


if __name__ == "__main__":
    unittest.main()
