import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "agents/sync-repo-config.py"

sys.path.insert(0, str(REPO_ROOT / "script"))
import helpers


def load_sync_module():
    spec = importlib.util.spec_from_file_location("sync_repo_config_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MiseTaskTomlParsingTests(unittest.TestCase):
    def test_parse_tasks_supports_valid_toml_forms(self):
        module = load_sync_module()
        content = '''
[tasks]
inline = "echo inline"
"quoted:name" = { run = "echo quoted" }

[tasks.multiline]
description = "A table declared across lines"
run = "echo multiline"
'''
        with tempfile.TemporaryDirectory() as tmpdir:
            mise_toml = Path(tmpdir) / ".mise.toml"
            mise_toml.write_text(content)
            self.assertEqual(
                module.parse_tasks(mise_toml),
                ["inline", "quoted:name", "multiline"],
            )

    def test_parse_tasks_ignores_non_task_tables(self):
        module = load_sync_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            mise_toml = Path(tmpdir) / ".mise.toml"
            mise_toml.write_text('[tools]\npython = "3.14"\n')
            self.assertEqual(module.parse_tasks(mise_toml), [])


class WriteGeneratedBackupTests(unittest.TestCase):
    """Cover the "regenerate always, never destroy without a backup" contract.

    Backups go through `helpers.backup_file`, so these tests patch
    `helpers.HOME`/`helpers.NOW` the same way `tests/test_installer_core.py`
    does for that helper, and reset dry-run state between tests.
    """

    def setUp(self):
        helpers.set_dry_run(False)
        self.addCleanup(helpers.set_dry_run, False)

    def test_overwrites_hand_written_file_after_backing_it_up(self):
        module = load_sync_module()
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            target = home / "repo" / ".claude" / "settings.json"
            target.parent.mkdir(parents=True)
            target.write_text("hand-written content")

            with (
                mock.patch.object(helpers, "HOME", home),
                mock.patch.object(helpers, "NOW", "timestamp"),
            ):
                module.write_generated(target, "generated content", False)

            self.assertEqual(target.read_text(), "generated content")
            backup = (
                home / ".dotfiles-backup" / "timestamp" / "repo" / ".claude"
                / "settings.json"
            )
            self.assertEqual(backup.read_text(), "hand-written content")

    def test_replaces_symlink_with_a_real_file_never_writing_through_it(self):
        module = load_sync_module()
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            elsewhere = Path(tmp) / "elsewhere" / "config"
            elsewhere.parent.mkdir(parents=True)
            elsewhere.write_text("outside the repo")
            target = home / "repo" / ".codex" / "rules" / "mise.rules"
            target.parent.mkdir(parents=True)
            target.symlink_to(elsewhere)

            with (
                mock.patch.object(helpers, "HOME", home),
                mock.patch.object(helpers, "NOW", "timestamp"),
            ):
                module.write_generated(target, "generated rules", False)

            # The write landed on a plain file at `target`, not through the
            # symlink to `elsewhere`.
            self.assertFalse(target.is_symlink())
            self.assertEqual(target.read_text(), "generated rules")
            self.assertEqual(elsewhere.read_text(), "outside the repo")

            backup = (
                home / ".dotfiles-backup" / "timestamp" / "repo" / ".codex"
                / "rules" / "mise.rules"
            )
            self.assertTrue(backup.is_symlink())
            self.assertEqual(backup.readlink(), elsewhere)

    def test_removes_existing_file_after_backup_when_nothing_to_generate(self):
        module = load_sync_module()
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            target = home / "repo" / ".opencode" / "opencode.json"
            target.parent.mkdir(parents=True)
            target.write_text("stale content")

            with (
                mock.patch.object(helpers, "HOME", home),
                mock.patch.object(helpers, "NOW", "timestamp"),
            ):
                module.write_generated(target, "", False)

            self.assertFalse(target.exists())
            backup = (
                home / ".dotfiles-backup" / "timestamp" / "repo" / ".opencode"
                / "opencode.json"
            )
            self.assertEqual(backup.read_text(), "stale content")

    def test_repeated_runs_do_not_collide_on_the_same_backup(self):
        module = load_sync_module()
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            target = home / "repo" / ".claude" / "settings.json"
            target.parent.mkdir(parents=True)
            target.write_text("version one")

            with (
                mock.patch.object(helpers, "HOME", home),
                mock.patch.object(helpers, "NOW", "timestamp"),
            ):
                module.write_generated(target, "version two", False)
                target.write_text("version three (hand-edited again)")
                module.write_generated(target, "version four", False)

            self.assertEqual(target.read_text(), "version four")
            backup_dir = home / ".dotfiles-backup" / "timestamp" / "repo" / ".claude"
            self.assertEqual((backup_dir / "settings.json").read_text(), "version one")
            self.assertEqual(
                (backup_dir / "settings.json.1").read_text(),
                "version three (hand-edited again)",
            )

    def test_dry_run_reports_without_changing_anything(self):
        module = load_sync_module()
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            target = home / "repo" / ".claude" / "settings.json"
            target.parent.mkdir(parents=True)
            target.write_text("hand-written content")

            with (
                mock.patch.object(helpers, "HOME", home),
                mock.patch.object(helpers, "NOW", "timestamp"),
            ):
                helpers.set_dry_run(True)
                module.write_generated(target, "generated content", True)

            self.assertEqual(target.read_text(), "hand-written content")
            self.assertFalse((home / ".dotfiles-backup").exists())

    def test_dry_run_reports_removal_without_changing_anything(self):
        module = load_sync_module()
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            target = home / "repo" / ".opencode" / "opencode.json"
            target.parent.mkdir(parents=True)
            target.write_text("stale content")

            with (
                mock.patch.object(helpers, "HOME", home),
                mock.patch.object(helpers, "NOW", "timestamp"),
            ):
                helpers.set_dry_run(True)
                module.write_generated(target, "", True)

            self.assertTrue(target.exists())
            self.assertEqual(target.read_text(), "stale content")
            self.assertFalse((home / ".dotfiles-backup").exists())

    def test_unchanged_content_is_left_alone_without_a_backup(self):
        module = load_sync_module()
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            target = home / "repo" / ".claude" / "settings.json"
            target.parent.mkdir(parents=True)
            target.write_text("same content")

            with (
                mock.patch.object(helpers, "HOME", home),
                mock.patch.object(helpers, "NOW", "timestamp"),
            ):
                module.write_generated(target, "same content", False)

            self.assertEqual(target.read_text(), "same content")
            self.assertFalse((home / ".dotfiles-backup").exists())


if __name__ == "__main__":
    unittest.main()
