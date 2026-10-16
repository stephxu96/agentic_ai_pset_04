"""review/check_content.sh: the machine checks and the review_id fingerprint."""
import hashlib
import json
import os
import unittest

import contracts
from harness import read_file, PipelineTest, to_jsonl, ts, days_before, AS_OF


def mentions_piece(issue, pid):
    for v in issue.values():
        if isinstance(v, str):
            low = v.lower()
            if v == pid or f"{pid}.md" in v or f"{pid}-c" in v or f"piece {pid}" in low or f"piece_id {pid}" in low:
                return True
    return False


def file_hash(path):
    return hashlib.sha256(read_file(path, "rb")).hexdigest()


class TestCheckContent(PipelineTest):
    REQUIRES = ["review/check_content.sh", "data/store.sh"]

    def setUp(self):
        super().setUp()
        self.rd = self.setup_or_error(self.sb.build_series_run)

    # -- helpers -----------------------------------------------------------
    def review(self):
        p, rev = self.sb.check(self.rd)
        self.assert_exit(p, 0, "a completed assessment exits 0 even when passed is false")
        self.assertIsNotNone(rev, f"stdout must be one JSON object{self.out(p)}")
        return rev

    def errors(self, rev):
        return [i for i in rev["issues"] if i.get("severity") == "error"]

    def briefs(self):
        return self.sb.read_jsonl(self.rd + "/briefs.jsonl")

    def save_briefs(self, briefs):
        self.sb.write_jsonl(self.rd + "/briefs.jsonl", briefs)

    def assert_blocked(self, rev, pid=None):
        self.assertFalse(rev["passed"], f"passed should be false; issues: {json.dumps(rev['issues'])[:500]}")
        self.assertTrue(self.errors(rev), "a blocking problem needs at least one issue with severity 'error'")
        if pid:
            self.assertTrue(any(mentions_piece(i, pid) for i in self.errors(rev)),
                            f"an error should identify piece {pid}: {json.dumps(self.errors(rev))[:500]}")

    # -- output shape ----------------------------------------------------------
    def test_valid_series_passes_with_required_fields(self):
        rev = self.review()
        for k in ("review_id", "passed", "issues"):
            self.assertIn(k, rev, f"review JSON needs '{k}'")
        self.assertTrue(contracts.nonempty_str(rev["review_id"]))
        self.assertIsInstance(rev["passed"], bool)
        self.assertIsInstance(rev["issues"], list)
        self.assertTrue(rev["passed"], f"a valid series should pass; issues: {json.dumps(rev['issues'])[:600]}")
        self.assertFalse(self.errors(rev), "a passing review has no error-severity issues")

    def test_short_drafts_trigger_length_warnings_with_a_usable_issue_shape(self):
        rev = self.review()
        warns = [i for i in rev["issues"] if i.get("severity") == "warning"]
        self.assertTrue(warns, "fixture articles are far below the 600-900 word target; expect length warnings")
        for i in rev["issues"]:
            self.assertIn(i.get("severity"), ("error", "warning"))
            blob = " ".join(i.keys()).lower()
            self.assertTrue(any(w in blob for w in ("piece", "artifact", "path", "file")),
                            f"each issue should identify its piece or artifact: {i}")
            self.assertTrue(any(w in blob for w in ("explan", "message", "detail", "description")),
                            f"each issue needs an explanation: {i}")
        text = json.dumps(warns).lower()
        self.assertTrue("word" in text or "length" in text, "expected a warning about the length target")

    def test_check_does_not_modify_drafts_or_briefs(self):
        paths = [self.rd + "/briefs.jsonl", self.rd + "/articles/01.md", self.rd + "/video_scripts/01.md",
                 self.rd + "/eligible.jsonl"]
        before = [file_hash(self.sb.path(p)) for p in paths]
        self.review()
        self.assertEqual(before, [file_hash(self.sb.path(p)) for p in paths], "check_content must be read-only")

    def test_missing_run_dir_argument_is_exit_2(self):
        self.assert_exit(self.sb.run("review/check_content.sh", []), 2)

    # -- review_id fingerprint -----------------------------------------------------
    def test_review_id_is_stable_for_identical_inputs(self):
        self.assertEqual(self.review()["review_id"], self.review()["review_id"])

    def test_review_id_changes_when_an_article_changes(self):
        a = self.review()["review_id"]
        self.sb.write(self.rd + "/articles/02.md", self.sb.read(self.rd + "/articles/02.md") + "\nAn extra sentence.\n")
        self.assertNotEqual(a, self.review()["review_id"])

    def test_review_id_changes_when_a_video_script_changes(self):
        a = self.review()["review_id"]
        self.sb.write(self.rd + "/video_scripts/03.md",
                      self.sb.read(self.rd + "/video_scripts/03.md") + "\nNarration: one more line.\n")
        self.assertNotEqual(a, self.review()["review_id"])

    def test_review_id_changes_when_a_brief_changes(self):
        a = self.review()["review_id"]
        b = self.briefs()
        b[0]["argument"] = "A different central argument."
        self.save_briefs(b)
        self.assertNotEqual(a, self.review()["review_id"])

    def test_review_id_changes_when_evidence_references_change(self):
        a = self.review()["review_id"]
        b = self.briefs()
        b[1]["claims"][0]["evidence"][0]["locator"]["quote"] = "completed 17 of 20 trials"
        self.save_briefs(b)
        self.assertNotEqual(a, self.review()["review_id"])

    def test_review_id_changes_when_the_as_of_date_changes(self):
        a = self.review()["review_id"]
        run = self.sb.read_json(self.rd + "/run.json")
        run["as_of_date"] = "2026-10-16"
        self.sb.write_json(self.rd + "/run.json", run)
        self.assertNotEqual(a, self.review()["review_id"])

    # -- blocking problems ----------------------------------------------------------
    def test_missing_article_is_a_blocking_error(self):
        os.remove(self.sb.path(self.rd + "/articles/02.md"))
        self.assert_blocked(self.review(), "02")

    def test_missing_video_script_is_a_blocking_error(self):
        os.remove(self.sb.path(self.rd + "/video_scripts/03.md"))
        self.assert_blocked(self.review(), "03")

    def test_fewer_than_three_briefs_is_a_blocking_error(self):
        self.save_briefs(self.briefs()[:2])
        self.assert_blocked(self.review())

    def test_quote_not_found_in_the_source_text_is_a_blocking_error(self):
        b = self.briefs()
        b[0]["claims"][0]["evidence"][0]["locator"]["quote"] = "a sentence that the source never contains"
        self.save_briefs(b)
        self.assert_blocked(self.review(), "01")

    def test_unknown_segment_id_is_a_blocking_error(self):
        b = self.briefs()
        b[1]["claims"][1]["evidence"][0]["locator"]["segment_id"] = "s999"
        self.save_briefs(b)
        self.assert_blocked(self.review(), "02")

    def test_claim_marker_missing_from_the_article_is_a_blocking_error(self):
        art = self.sb.read(self.rd + "/articles/01.md").replace("[01-c2]", "")
        self.sb.write(self.rd + "/articles/01.md", art)
        self.assert_blocked(self.review(), "01")

    def test_manifest_claim_unknown_to_the_brief_is_a_blocking_error(self):
        m = self.sb.read_jsonl(self.rd + "/articles.jsonl")
        m[2]["claim_ids"].append("03-c99")
        self.sb.write_jsonl(self.rd + "/articles.jsonl", m)
        self.assert_blocked(self.review(), "03")

    def test_article_and_script_disagreeing_on_claims_is_flagged(self):
        m = self.sb.read_jsonl(self.rd + "/video_scripts.jsonl")
        m[0]["claim_ids"] = m[0]["claim_ids"][:-1]
        self.sb.write_jsonl(self.rd + "/video_scripts.jsonl", m)
        rev = self.review()
        flagged = [i for i in rev["issues"] if mentions_piece(i, "01") or "consisten" in json.dumps(i).lower()]
        self.assertTrue(flagged, "article/script inconsistency for piece 01 should be reported (any severity)")

    def test_evidence_from_a_source_outside_the_window_is_a_blocking_error(self):
        b = self.briefs()
        old = self.sb.read_jsonl(self.rd + "/exclusions.jsonl")[0]
        b[0]["claims"][0]["evidence"][0] = {
            "item_id": old["item_id"], "version_id": old["version_id"],
            "locator": {"type": "text", "quote": "completed 17 of 20 trials under the stated conditions"}}
        self.save_briefs(b)
        self.assert_blocked(self.review(), "01")

    def test_piece_with_fewer_than_three_independent_publishers_is_a_blocking_error(self):
        items = {i["item_id"]: i for i in self.sb.read_jsonl(self.rd + "/eligible.jsonl")}
        q = "completed 17 of 20 trials under the stated conditions"

        def txt(i):
            return {"item_id": i["item_id"], "version_id": i["version_id"], "locator": {"type": "text", "quote": q}}

        def seg(i):
            return {"item_id": i["item_id"], "version_id": i["version_id"], "locator": {"type": "segment", "segment_id": "s1"}}

        b = self.briefs()
        # a1 and p4 share publisher pub-a, so piece 01 now rests on only two publishers
        b[0]["claims"][0]["evidence"] = [txt(items["feed:a1"])]
        b[0]["claims"][1]["evidence"] = [seg(items["podcast:p4"])]
        b[0]["claims"][2]["evidence"] = [txt(items["feed:a1"]), seg(items["podcast:p4"]), seg(items["youtube:y1"])]
        b[0]["claims"][1]["evidence"][0]["locator"]["segment_id"] = "s1"
        # youtube:y1 is pub-f, so this is exactly two publishers
        self.save_briefs(b)
        self.assert_blocked(self.review(), "01")

    def test_series_with_no_podcast_evidence_is_a_blocking_error(self):
        items = {i["item_id"]: i for i in self.sb.read_jsonl(self.rd + "/eligible.jsonl")}
        a3 = items["feed:a3"]
        q = "completed 17 of 20 trials under the stated conditions"
        b = self.briefs()
        for br in b:
            for cl in br["claims"]:
                cl["evidence"] = [ev if not ev["item_id"].startswith("podcast:") else
                                  {"item_id": a3["item_id"], "version_id": a3["version_id"],
                                   "locator": {"type": "text", "quote": q}} for ev in cl["evidence"]]
        self.save_briefs(b)
        rev = self.review()
        self.assertFalse(rev["passed"], "media coverage across the series is required (written, video and podcast)")
        self.assertTrue(self.errors(rev))


if __name__ == "__main__":
    unittest.main()
