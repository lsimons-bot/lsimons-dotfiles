"""Focused tests for platform-specific installer failure and first-run behavior."""

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "script"))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


terminal_installer = load_module(
    "dotfiles_terminal_platform", REPO_ROOT / "terminal" / "install.py"
)
mise_installer = load_module(
    "dotfiles_mise_platform", REPO_ROOT / "mise" / "install.py"
)
go_installer = load_module("dotfiles_go_platform", REPO_ROOT / "go" / "install.py")


class TerminalInstallerTests(unittest.TestCase):
    def test_platform_terminal_creates_fresh_preferences_domain(self):
        missing = subprocess.CompletedProcess(
            [], 1, stdout="", stderr="Domain com.apple.Terminal does not exist"
        )
        imported = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with mock.patch.object(
            terminal_installer.subprocess, "run", side_effect=[missing, imported]
        ) as run:
            self.assertTrue(terminal_installer.import_profile({"name": "test"}))
        self.assertEqual(run.call_args_list[1].args[0][0:2], ["defaults", "import"])

    def test_platform_terminal_preserves_other_export_failures(self):
        failed = subprocess.CompletedProcess([], 1, stdout="", stderr="permission denied")
        with mock.patch.object(terminal_installer.subprocess, "run", return_value=failed):
            self.assertFalse(terminal_installer.import_profile({"name": "test"}))


class MiseInstallerTests(unittest.TestCase):
    def test_platform_mise_propagates_launchctl_load_failure(self):
        failed = subprocess.CompletedProcess([], 1, stdout="", stderr="load failed")
        with tempfile.TemporaryDirectory() as home, mock.patch.object(
            mise_installer.Path, "home", return_value=Path(home)
        ), mock.patch.object(mise_installer, "run_cmd", return_value=failed):
            self.assertFalse(mise_installer.install_launch_agent())

    def test_platform_mise_main_propagates_configuration_failure(self):
        with mock.patch.object(mise_installer, "parse_dry_run"), mock.patch.object(
            mise_installer, "install_mise", return_value=True
        ), mock.patch.object(
            mise_installer, "ensure_minimum_release_age", return_value=False
        ), mock.patch.object(mise_installer, "install_gui_path_hook") as hook:
            self.assertEqual(mise_installer.main(), 1)
            hook.assert_not_called()

    def test_platform_mise_main_propagates_gui_path_hook_failure(self):
        with mock.patch.object(mise_installer, "parse_dry_run"), mock.patch.object(
            mise_installer, "install_mise", return_value=True
        ), mock.patch.object(
            mise_installer, "ensure_minimum_release_age", return_value=True
        ), mock.patch.object(
            mise_installer, "install_gui_path_hook", return_value=False
        ):
            self.assertEqual(mise_installer.main(), 1)

    def test_platform_mise_gui_path_hook_dispatches_per_platform(self):
        """macOS gets the LaunchAgent, Linux the environment.d drop-in."""
        for is_macos, expected, other in (
            (True, "install_launch_agent", "install_environment_d"),
            (False, "install_environment_d", "install_launch_agent"),
        ):
            with self.subTest(macos=is_macos), mock.patch.object(
                mise_installer, "IS_MACOS", is_macos
            ), mock.patch.object(
                mise_installer, "IS_LINUX", not is_macos
            ), mock.patch.object(
                mise_installer, expected, return_value=True
            ) as chosen, mock.patch.object(mise_installer, other) as skipped:
                self.assertTrue(mise_installer.install_gui_path_hook())
                chosen.assert_called_once()
                skipped.assert_not_called()

    def test_platform_mise_environment_d_prepends_to_existing_path(self):
        """The drop-in must extend systemd's PATH, not replace it."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "environment.d" / "10-mise-shims.conf"
            with mock.patch.object(
                mise_installer, "ENVIRONMENT_D_FILE", target
            ), mock.patch.object(mise_installer, "is_dry_run", return_value=False):
                self.assertTrue(mise_installer.install_environment_d())
                first = target.read_text()
                # Second run must be a no-op, not a duplicated entry.
                self.assertTrue(mise_installer.install_environment_d())

        self.assertIn("mise/shims", first)
        self.assertTrue(first.rstrip().endswith(":${PATH}"))
        self.assertEqual(first.count("PATH="), 1)


class PrerequisiteGuardTests(unittest.TestCase):
    def test_platform_mise_prerequisite_is_nonfatal_during_dry_run(self):
        with mock.patch.object(go_installer, "parse_dry_run"), mock.patch.object(
            go_installer, "command_exists", return_value=False
        ), mock.patch.object(go_installer, "is_dry_run", return_value=True), mock.patch.object(
            go_installer, "mise_use", return_value=True
        ):
            self.assertEqual(go_installer.main(), 0)


if __name__ == "__main__":
    unittest.main()


terraform_installer = load_module(
    "dotfiles_terraform_platform", REPO_ROOT / "terraform" / "install.py"
)


class TerraformInstallerTests(unittest.TestCase):
    """The Arch tfenv package needs a writable config dir and the tfenv group."""

    def test_platform_terraform_arch_sets_config_dir_without_prompting(self):
        with mock.patch.object(terraform_installer, "IS_ARCH", True):
            cmd = terraform_installer.tfenv_command(["install", "latest"], group_active=True)
        self.assertEqual(cmd[0], "env")
        self.assertTrue(cmd[1].startswith("TFENV_CONFIG_DIR="))
        self.assertEqual(cmd[2:], ["tfenv", "install", "latest"])

    def test_platform_terraform_arch_borrows_group_until_relogin(self):
        with mock.patch.object(terraform_installer, "IS_ARCH", True), mock.patch.object(
            terraform_installer.getpass, "getuser", return_value="someone"
        ):
            cmd = terraform_installer.tfenv_command(["use", "latest"], group_active=False)
        self.assertEqual(cmd[:5], ["sudo", "-u", "someone", "-g", "tfenv"])
        self.assertEqual(cmd[-3:], ["tfenv", "use", "latest"])

    def test_platform_terraform_other_platforms_call_tfenv_directly(self):
        with mock.patch.object(terraform_installer, "IS_ARCH", False):
            cmd = terraform_installer.tfenv_command(["install", "latest"], group_active=True)
        self.assertEqual(cmd, ["tfenv", "install", "latest"])
