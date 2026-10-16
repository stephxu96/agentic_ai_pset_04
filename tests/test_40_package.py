"""publishing/prepare_package.sh: it must refuse stale or unapproved work and preserve entered links."""
import hashlib
import json
import os
import unittest

from harness import read_file, PipelineTest, AS_OF


def sha_file(path):
    return hashlib.sha256(read_file(path, "rb")).hexdigest()


class TestPreparePackage(PipelineTest):
    REQUIRES = ["publishing/prepare_package.sh", "review/check_content.sh", "data/store.sh"]

    def setUp(self):
        super().setUp()
        self.rd = self.setup_or_error(self.sb.build_series_run)

    # -- helpers -----------------------------------------------------------
    def approved(self, decision="approve"):
        """Run the check, save review.json, and record a human approval for that review."""
        p, rev = self.sb.check(self.rd)
        self.assert_exit(p, 0)
        self.assertIsNotNone(rev, "check_content must emit JSON (needed to set up this test)")
        self.sb.write_json(self.rd + "/review.json", rev)
        self.sb.approve(self.rd, rev["review_id"], decision=decision)
        return rev

    def package(self):
        return self.sb.run("publishing/prepare_package.sh", [self.rd])

    def assert_refused(self, p, why):
        self.assert_exit(p, 1, why)
        self.assertTrue(p.stderr.strip(), "refusal should explain what is missing or stale on stderr")
        self.assertFalse(self.sb.exists(self.rd + "/package/manifest.json"), "no manifest may be produced on refusal")

    def package_files(self):
        base = self.sb.path(self.rd + "/package")
        out = []
        for dp, _, fns in os.walk(base):
            for fn in fns:
                out.append(os.path.join(dp, fn))
        return out

    # -- refusals ------------------------------------------------------------
    def test_refuses_without_an_approval(self):
        p, rev = self.sb.check(self.rd)
        self.sb.write_json(self.rd + "/review.json", rev)
        self.assert_refused(self.package(), "no approval.json yet")

    def test_refuses_when_the_decision_is_revise(self):
        self.approved(decision="revise")
        self.assert_refused(self.package(), "decision is revise")

    def test_refuses_when_approval_is_for_a_different_review(self):
        rev = self.approved()
        self.sb.approve(self.rd, rev["review_id"] + "-stale")
        self.assert_refused(self.package(), "review_id does not match")

    def test_refuses_when_the_review_did_not_pass(self):
        os.remove(self.sb.path(self.rd + "/articles/02.md"))
        p, rev = self.sb.check(self.rd)
        self.assertIsNotNone(rev)
        self.assertFalse(rev["passed"], "setup: removing an article should fail the review")
        self.sb.write_json(self.rd + "/review.json", rev)
        self.sb.approve(self.rd, rev["review_id"])
        self.assert_refused(self.package(), "a failing review cannot be approved into a package")

    def test_refuses_when_an_article_changed_after_approval(self):
        self.approved()
        self.sb.write(self.rd + "/articles/01.md", self.sb.read(self.rd + "/articles/01.md") + "\nEdited after review.\n")
        self.assert_refused(self.package(), "reviewed inputs changed; this must hold even when invoked directly")

    def test_refuses_when_a_brief_changed_after_approval(self):
        self.approved()
        b = self.sb.read_jsonl(self.rd + "/briefs.jsonl")
        b[1]["argument"] = "Changed after approval."
        self.sb.write_jsonl(self.rd + "/briefs.jsonl", b)
        self.assert_refused(self.package(), "briefs changed after approval")

    def test_missing_run_dir_argument_is_exit_2(self):
        self.assert_exit(self.sb.run("publishing/prepare_package.sh", []), 2)

    # -- a successful package ---------------------------------------------------------
    def test_approved_run_produces_a_package_with_a_manifest_on_stdout(self):
        self.approved()
        p = self.package()
        self.assert_exit(p, 0)
        try:
            printed = json.loads(p.stdout)
        except json.JSONDecodeError:
            self.fail(f"stdout must be the manifest JSON{self.out(p)}")
        self.assertTrue(self.sb.exists(self.rd + "/package/manifest.json"))
        self.assertEqual(printed, self.sb.read_json(self.rd + "/package/manifest.json"),
                         "stdout and package/manifest.json should be the same manifest")
        text = json.dumps(printed)
        for pid in ("01", "02", "03"):
            self.assertIn(pid, text, f"manifest should list piece {pid}")
        for f in self.package_files():
            base = os.path.basename(f)
            if base != "manifest.json":
                self.assertIn(base, text, f"manifest should list package asset {base}")

    def test_package_contains_reviewed_articles_and_scripts_unmodified(self):
        self.approved()
        self.assert_exit(self.package(), 0)
        hashes = {sha_file(f) for f in self.package_files()}
        for pid in ("01", "02", "03"):
            for kind in ("articles", "video_scripts"):
                h = sha_file(self.sb.path(f"{self.rd}/{kind}/{pid}.md"))
                self.assertIn(h, hashes, f"package should hold an unmodified copy of {kind}/{pid}.md")

    def test_package_has_source_notes_manifest_and_links_files(self):
        self.approved()
        self.assert_exit(self.package(), 0)
        files = self.package_files()
        self.assertTrue(self.sb.exists(self.rd + "/package/publication_links.json"))
        self.assertGreaterEqual(len(files), 11,
                                "expect 3 articles + 3 scripts + 3 source notes + manifest.json + publication_links.json")

    def test_publication_links_start_as_null_for_every_piece(self):
        self.approved()
        self.assert_exit(self.package(), 0)
        recs = self.sb.read_json(self.rd + "/package/publication_links.json")
        if isinstance(recs, dict):
            recs = next((v for v in recs.values() if isinstance(v, list)), [])
        self.assertEqual(sorted(r["piece_id"] for r in recs), ["01", "02", "03"])
        for r in recs:
            self.assertIsNone(r["substack_url"], "unpublished URLs initialize to null")
            self.assertIsNone(r["youtube_url"])

    def test_package_states_the_remaining_manual_steps(self):
        self.approved()
        self.assert_exit(self.package(), 0)
        draft_hashes = {sha_file(self.sb.path(f"{self.rd}/{k}/{p}.md"))
                        for k in ("articles", "video_scripts") for p in ("01", "02", "03")}
        notes = ""
        for f in self.package_files():
            if sha_file(f) not in draft_hashes and not f.endswith("publication_links.json"):
                notes += read_file(f).lower()
        for needle, label in (("substack", "Substack"), ("youtube", "YouTube")):
            self.assertIn(needle, notes, f"the package must say the {label} step is still manual")
        self.assertTrue("powerpoint" in notes and "chatterbox" in notes, "must describe the PowerPoint and Chatterbox video production step")

    def test_does_not_modify_the_reviewed_drafts(self):
        self.approved()
        paths = [self.rd + "/articles/01.md", self.rd + "/video_scripts/02.md", self.rd + "/briefs.jsonl"]
        before = [sha_file(self.sb.path(p)) for p in paths]
        self.assert_exit(self.package(), 0)
        self.assertEqual(before, [sha_file(self.sb.path(p)) for p in paths])

    # -- repackaging ------------------------------------------------------------------
    def test_repackaging_an_unchanged_run_preserves_entered_publication_links(self):
        self.approved()
        self.assert_exit(self.package(), 0)
        path = self.rd + "/package/publication_links.json"
        recs = self.sb.read_json(path)
        holder = recs
        if isinstance(recs, dict):
            holder = next(v for v in recs.values() if isinstance(v, list))
        for r in holder:
            if r["piece_id"] == "01":
                r["substack_url"] = "https://example.substack.com/p/piece-one"
                r["youtube_url"] = "https://youtu.be/example1"
        self.sb.write_json(path, recs)
        self.assert_exit(self.package(), 0, "repackaging an unchanged run")
        after = self.sb.read_json(path)
        if isinstance(after, dict):
            after = next(v for v in after.values() if isinstance(v, list))
        piece1 = next(r for r in after if r["piece_id"] == "01")
        self.assertEqual(piece1["substack_url"], "https://example.substack.com/p/piece-one",
                         "entered publication links must survive repackaging")
        self.assertEqual(piece1["youtube_url"], "https://youtu.be/example1")


if __name__ == "__main__":
    unittest.main()
