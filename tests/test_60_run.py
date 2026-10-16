"""run.sh: configuration validation (exit 2) and --package mode. No network is used."""
import hashlib
import json
import os
import shutil
import unittest

from harness import read_file, PipelineTest


def sha_file(path):
    return hashlib.sha256(read_file(path, "rb")).hexdigest()


class TestRunConfigValidation(PipelineTest):
    """These tests assume run.sh validates configuration before doing any collection or tool checks."""
    REQUIRES = ["run.sh"]

    def setUp(self):
        super().setUp()
        shutil.copytree(os.path.join(self.sb.repo, "config"), self.sb.path("config"), dirs_exist_ok=True)

    def run_sh(self, *args):
        return self.sb.run("run.sh", list(args), timeout=60)

    def edit_project(self, **changes):
        cfg = self.sb.read_json("config/project.json")
        cfg.update(changes)
        self.sb.write_json("config/project.json", cfg)

    def test_empty_audience_is_exit_2(self):
        self.edit_project(audience="")
        self.assert_exit(self.run_sh(), 2, "project.json audience must be a nonempty string")

    def test_empty_central_question_is_exit_2(self):
        self.edit_project(central_question="   ")
        self.assert_exit(self.run_sh(), 2)

    def test_missing_project_json_is_exit_2(self):
        os.remove(self.sb.path("config/project.json"))
        self.assert_exit(self.run_sh(), 2)

    def test_malformed_project_json_is_exit_2(self):
        self.sb.write("config/project.json", "{ not json")
        self.assert_exit(self.run_sh(), 2)

    def test_unknown_source_kind_is_exit_2(self):
        src = self.sb.read_json("config/sources.json")
        src[0]["kind"] = "rss"
        self.sb.write_json("config/sources.json", src)
        self.assert_exit(self.run_sh(), 2, "kind must be feed, youtube or podcast")

    def test_source_without_publisher_id_is_exit_2(self):
        src = self.sb.read_json("config/sources.json")
        del src[0]["publisher_id"]
        self.sb.write_json("config/sources.json", src)
        self.assert_exit(self.run_sh(), 2)

    def test_missing_editorial_policy_is_exit_2(self):
        os.remove(self.sb.path("config/editorial_policy.md"))
        self.assert_exit(self.run_sh(), 2)

    def test_package_flag_without_a_run_dir_is_exit_2(self):
        self.assert_exit(self.run_sh("--package"), 2)

    def test_package_flag_with_a_nonexistent_run_dir_is_exit_2(self):
        self.assert_exit(self.run_sh("--package", "runs/does-not-exist"), 2)


class TestRunPackageMode(PipelineTest):
    REQUIRES = ["run.sh", "review/check_content.sh", "publishing/prepare_package.sh",
                "reporting/summarize_run.sh", "data/store.sh"]

    def setUp(self):
        super().setUp()
        shutil.copytree(os.path.join(self.sb.repo, "config"), self.sb.path("config"), dirs_exist_ok=True)
        self.rd = self.setup_or_error(self.sb.build_series_run)

    def frozen(self):
        names = ["candidates.jsonl", "items.jsonl", "eligible.jsonl", "decisions.jsonl", "briefs.jsonl",
                 "articles/01.md", "articles/02.md", "articles/03.md",
                 "video_scripts/01.md", "video_scripts/02.md", "video_scripts/03.md", "run.json"]
        return {n: sha_file(self.sb.path(f"{self.rd}/{n}")) for n in names}

    def test_package_mode_with_approval_packages_without_recollecting_or_regenerating(self):
        p, rev = self.sb.check(self.rd)
        self.assertIsNotNone(rev)
        self.sb.write_json(self.rd + "/review.json", rev)
        self.sb.approve(self.rd, rev["review_id"])
        before = self.frozen()
        p = self.sb.run("run.sh", ["--package", self.rd], timeout=120)
        self.assert_exit(p, 0)
        self.assertEqual(before, self.frozen(),
                         "--package must leave sources, drafts and snapshots unchanged (no recollection, no regeneration)")
        self.assertTrue(self.sb.exists(self.rd + "/package/manifest.json"))
        self.assertTrue(self.sb.exists(self.rd + "/summary.json"), "the summary is refreshed and saved")
        try:
            printed = json.loads(p.stdout)
        except json.JSONDecodeError:
            self.fail(f"run.sh prints the resulting summary JSON on stdout{self.out(p)}")
        self.assertEqual(printed.get("status"), "ready_for_production")

    def test_package_mode_without_approval_fails_and_creates_no_package(self):
        p = self.sb.run("run.sh", ["--package", self.rd], timeout=120)
        self.assertNotEqual(p.returncode, 0, f"packaging without an approval must not succeed{self.out(p)}")
        self.assertFalse(self.sb.exists(self.rd + "/package/manifest.json"))


if __name__ == "__main__":
    unittest.main()
