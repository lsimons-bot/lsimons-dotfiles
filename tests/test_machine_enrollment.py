"""Tests for machine-enrollment fail-fast behavior (GitHub issue #8).

get_machine_config() must refuse to fall back to machines/default.json when
the current hostname has no dedicated machines/<hostname>.json: that file
intentionally has no SSH keys and no git signing key, and silently using it
for an unenrolled machine previously produced a broken (signing-enabled but
keyless) git config and suppressed the 1Password SSH agent's normal key
exposure.
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "script"))

import helpers


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


git_installer = load_module(
    "dotfiles_git_installer_enrollment", REPO_ROOT / "git" / "install.py"
)
onepassword = load_module(
    "dotfiles_onepassword_installer_enrollment", REPO_ROOT / "1password" / "install.py"
)


def _reset_machine_cache():
    # Not inside a class body, so this plain attribute name isn't mangled.
    helpers.__machine_config = None


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def _completed_process(returncode=0, stderr=""):
    """Stand-in for a run_cmd() result, so tests never shell out for real."""
    return subprocess.CompletedProcess(args=[], returncode=returncode, stderr=stderr)


class GetMachineConfigTests(unittest.TestCase):
    """Direct tests of helpers.get_machine_config()."""

    def setUp(self):
        helpers.set_dry_run(False)
        _reset_machine_cache()
        self.addCleanup(_reset_machine_cache)

    def test_missing_host_file_exits_nonzero_with_clear_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "machines" / "default.json", {"git": {"user": {}}})

            with (
                mock.patch.object(helpers, "DOTFILES_ROOT", root),
                mock.patch.dict(
                    helpers.os.environ,
                    {helpers.MACHINE_HOSTNAME_ENV: "unknown-laptop"},
                ),
                mock.patch.object(helpers, "error") as error_mock,
                self.assertRaises(SystemExit) as cm,
            ):
                helpers.get_machine_config()

            self.assertEqual(cm.exception.code, 1)
            messages = " ".join(call.args[0] for call in error_mock.call_args_list)
            self.assertIn("unknown-laptop", messages)
            self.assertIn("unknown-laptop.json", messages)

    def test_existing_host_file_merges_as_before(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(
                root / "machines" / "default.json",
                {"git": {"user": {"name": "Default", "email": "d@example.com", "signingkey": None}}},
            )
            _write_json(
                root / "machines" / "known-laptop.json",
                {"git": {"user": {"signingkey": "some-key"}}},
            )

            with (
                mock.patch.object(helpers, "DOTFILES_ROOT", root),
                mock.patch.dict(
                    helpers.os.environ,
                    {helpers.MACHINE_HOSTNAME_ENV: "known-laptop"},
                ),
            ):
                config, hostname = helpers.get_machine_config()

            self.assertEqual(hostname, "known-laptop")
            self.assertEqual(
                config,
                {
                    "git": {
                        "user": {
                            "name": "Default",
                            "email": "d@example.com",
                            "signingkey": "some-key",
                        }
                    }
                },
            )

    def test_result_is_cached_after_first_successful_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "machines" / "default.json", {"git": {"user": {}}})
            _write_json(root / "machines" / "known-laptop.json", {})

            with (
                mock.patch.object(helpers, "DOTFILES_ROOT", root),
                mock.patch.dict(
                    helpers.os.environ,
                    {helpers.MACHINE_HOSTNAME_ENV: "known-laptop"},
                ),
            ):
                first = helpers.get_machine_config()
                # Even if the hostname override changes afterwards, the
                # cached result from the first call is reused.
                with mock.patch.dict(
                    helpers.os.environ, {helpers.MACHINE_HOSTNAME_ENV: "unknown-laptop"}
                ):
                    second = helpers.get_machine_config()

            self.assertIs(first, second)


class GitInstallerEnrollmentTests(unittest.TestCase):
    """git/install.py must check enrollment before touching any files."""

    def test_main_aborts_before_migrating_legacy_files_when_unenrolled(self):
        with (
            mock.patch.object(
                git_installer, "get_machine_config", side_effect=SystemExit(1)
            ),
            mock.patch.object(git_installer, "migrate_legacy_files") as migrate,
            mock.patch.object(git_installer, "generate_config") as generate,
            mock.patch.object(git_installer, "generate_allowed_signers") as signers,
            self.assertRaises(SystemExit) as cm,
        ):
            git_installer.main()

        self.assertEqual(cm.exception.code, 1)
        migrate.assert_not_called()
        generate.assert_not_called()
        signers.assert_not_called()

    def test_main_proceeds_normally_when_enrolled(self):
        machine = {
            "git": {"user": {"name": "Test User", "email": "t@example.com", "signingkey": None}}
        }
        with (
            mock.patch.object(
                git_installer, "get_machine_config", return_value=(machine, "known-laptop")
            ),
            mock.patch.object(git_installer, "migrate_legacy_files") as migrate,
            mock.patch.object(git_installer, "generate_config") as generate,
            mock.patch.object(git_installer, "generate_allowed_signers") as signers,
            mock.patch.object(git_installer, "brew_is_installed", return_value=True),
            # main() ends by shelling out to `git lfs install --skip-repo`.
            # Left unmocked that is a real subprocess: it fails this test on
            # any machine without git-lfs, and on a machine *with* git-lfs it
            # writes filter.lfs.* into the user's global ~/.gitconfig. A unit
            # test must neither depend on nor mutate host state.
            mock.patch.object(
                git_installer, "run_cmd", return_value=_completed_process()
            ) as run_cmd,
        ):
            result = git_installer.main()

        run_cmd.assert_called_once_with(
            ["git", "lfs", "install", "--skip-repo"], check=False, capture_output=True
        )
        self.assertEqual(result, 0)
        migrate.assert_called_once()
        generate.assert_called_once()
        signers.assert_called_once()


class OnePasswordInstallerEnrollmentTests(unittest.TestCase):
    """1password/install.py must check enrollment before touching any files."""

    def test_main_aborts_before_migrating_legacy_config_dir_when_unenrolled(self):
        with (
            mock.patch.object(
                onepassword, "get_machine_config", side_effect=SystemExit(1)
            ),
            mock.patch.object(onepassword, "migrate_legacy_config_dir") as migrate,
            mock.patch.object(
                onepassword, "install_1password_ssh_agent_config"
            ) as install_agent,
            self.assertRaises(SystemExit) as cm,
        ):
            onepassword.main()

        self.assertEqual(cm.exception.code, 1)
        migrate.assert_not_called()
        install_agent.assert_not_called()

    def test_main_proceeds_normally_when_enrolled(self):
        machine = {"ssh": {"keys": []}}
        with (
            mock.patch.object(
                onepassword, "get_machine_config", return_value=(machine, "known-laptop")
            ),
            mock.patch.object(onepassword, "migrate_legacy_config_dir") as migrate,
            mock.patch.object(
                onepassword, "install_1password_ssh_agent_config"
            ) as install_agent,
            mock.patch("pathlib.Path.exists", return_value=True),
            mock.patch.object(onepassword, "command_exists", return_value=True),
        ):
            result = onepassword.main()

        self.assertEqual(result, 0)
        migrate.assert_called_once()
        install_agent.assert_called_once()


if __name__ == "__main__":
    unittest.main()
