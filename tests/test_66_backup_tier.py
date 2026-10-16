"""Backup-tier sources run only with --with-backup; inactive sources are excluded with a reason."""
import json, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "workflows"))
sys.path.insert(0, str(ROOT / "processing"))
import run_pipeline  # noqa: E402
import filter_items  # noqa: E402


class BackupTier(unittest.TestCase):
    def snapshot(self, include_backup):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "config").mkdir()
        (tmp / "prompts").mkdir()
        for p in (ROOT / "config").iterdir():
            if p.is_file():
                shutil.copy2(p, tmp / "config" / p.name)
        for p in (ROOT / "prompts").iterdir():
            if p.is_file():
                shutil.copy2(p, tmp / "prompts" / p.name)
        old = run_pipeline.ROOT
        run_pipeline.ROOT = tmp
        try:
            _, run_path = run_pipeline.create_run(
                run_pipeline.validate_config(), include_backup=include_backup,
                extra={"include_backup": include_backup})
        finally:
            run_pipeline.ROOT = old
        return run_path

    def ids(self, run_path):
        return {x["source_id"] for x in json.loads((run_path / "config" / "sources.json").read_text())}

    def test_default_run_skips_backup(self):
        ids = self.ids(self.snapshot(False))
        self.assertNotIn("cadalyst", ids)
        self.assertIn("engineering-com-ai", ids)

    def test_with_backup_includes_all(self):
        self.assertIn("cadalyst", self.ids(self.snapshot(True)))

    def test_active_set_only_for_live_runs_that_record_a_tier(self):
        run_path = self.snapshot(False)
        self.assertNotIn("cadalyst", filter_items.active_source_ids(run_path))
        meta = json.loads((run_path / "run.json").read_text())
        meta.pop("include_backup")
        (run_path / "run.json").write_text(json.dumps(meta))
        self.assertIsNone(filter_items.active_source_ids(run_path))


if __name__ == "__main__":
    unittest.main()
