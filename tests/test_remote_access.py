"""Tests for the opt-in remote-access topics (sshd, sunshine) and the
`remoteAccess` machine-config block that gates them.

The costly mistakes here are all lock-outs or surprise exposure: turning
off password login before a key is authorized, running the host topics
on a machine that never asked for them, and a typo in the machine config
silently disabling the gate. So that is what these cover.
"""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "script"))

import check
import helpers


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sshd = load_module("dotfiles_sshd", REPO_ROOT / "sshd" / "install.py")
sunshine = load_module("dotfiles_sunshine", REPO_ROOT / "sunshine" / "install.py")

KEY_A = "ssh-ed25519 AAAAexampleA a@example"
KEY_B = "ssh-ed25519 AAAAexampleB b@example"


class RemoteAccessSchemaTests(unittest.TestCase):
    def test_accepts_the_snow_shaped_block(self):
        errors = check.validate_machine_data(
            {
                "remoteAccess": {
                    "allowFrom": "192.168.2.0/24",
                    "sshd": True,
                    "sunshine": True,
                    "vaapiDriver": "libva-intel-driver",
                }
            },
            "machine.json",
        )
        self.assertEqual(errors, [])

    def test_rejects_stringly_typed_flags_and_unknown_keys(self):
        errors = check.validate_machine_data(
            {"remoteAccess": {"sshd": "yes", "moonlight": True}}, "machine.json"
        )
        self.assertIn("machine.json:$.remoteAccess.sshd: must be a bool", errors)
        self.assertIn("machine.json:$.remoteAccess.moonlight: unknown key", errors)


class GateTests(unittest.TestCase):
    def test_sshd_skips_when_not_enabled(self):
        with mock.patch.object(sshd, "parse_dry_run"), mock.patch.object(
            sshd, "get_remote_access_config", return_value={}
        ), mock.patch.object(sshd, "install_server") as install:
            self.assertEqual(sshd.main(), 0)
        install.assert_not_called()

    def test_sunshine_skips_when_not_enabled(self):
        with mock.patch.object(sunshine, "parse_dry_run"), mock.patch.object(
            sunshine, "get_remote_access_config", return_value={"sshd": True}
        ), mock.patch.object(sunshine, "install_sunshine") as install:
            self.assertEqual(sunshine.main(), 0)
        install.assert_not_called()


class AuthorizedKeysTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        ssh_dir = Path(self.tmp.name) / ".ssh"
        self.path = ssh_dir / "authorized_keys"
        patcher = mock.patch.multiple(
            sshd, SSH_CONFIG_DIR=ssh_dir, AUTHORIZED_KEYS=self.path
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        helpers.set_dry_run(False)

    def test_only_auth_keys_are_selected(self):
        with mock.patch.object(
            sshd,
            "get_machine_ssh_config",
            return_value={
                "keys": [
                    {"public_key": KEY_A, "auth": True},
                    {"public_key": KEY_B, "auth": False},
                ]
            },
        ):
            self.assertEqual(sshd.authorized_public_keys(), [KEY_A])

    def test_appends_without_duplicating_or_dropping_manual_keys(self):
        self.path.parent.mkdir()
        self.path.write_text(f"# by hand\n{KEY_B}\n")
        self.assertEqual(sshd.install_authorized_keys([KEY_A, KEY_B]), 2)
        self.assertEqual(sshd.install_authorized_keys([KEY_A, KEY_B]), 2)
        self.assertEqual(
            self.path.read_text().splitlines(), ["# by hand", KEY_B, KEY_A]
        )
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_dry_run_writes_nothing(self):
        helpers.set_dry_run(True)
        self.addCleanup(helpers.set_dry_run, False)
        self.assertEqual(sshd.install_authorized_keys([KEY_A]), 1)
        self.assertFalse(self.path.exists())


class HardeningTests(unittest.TestCase):
    def test_password_login_stays_on_without_a_key(self):
        with mock.patch.object(sshd, "sudo_write_file") as write:
            self.assertTrue(sshd.harden(0))
        write.assert_not_called()

    def test_reloads_sshd_only_when_the_snippet_changed(self):
        ok = mock.Mock(returncode=0, stderr="")
        with mock.patch.object(sshd, "sudo_write_file", return_value=False), mock.patch.object(
            sshd, "run_cmd", return_value=ok
        ) as run:
            self.assertTrue(sshd.harden(1))
        run.assert_not_called()
        with mock.patch.object(sshd, "sudo_write_file", return_value=True), mock.patch.object(
            sshd, "run_cmd", return_value=ok
        ) as run:
            self.assertTrue(sshd.harden(1))
        self.assertEqual(run.call_args.args[0][:3], ["sudo", "systemctl", "reload"])


class SunshineTests(unittest.TestCase):
    def test_udev_is_reloaded_only_on_a_fresh_install(self):
        with mock.patch.object(sunshine, "ensure_package", return_value=True), mock.patch.object(
            sunshine, "pacman_is_installed", return_value=True
        ), mock.patch.object(sunshine, "reload_udev") as reload:
            self.assertTrue(sunshine.install_sunshine())
        reload.assert_not_called()
        with mock.patch.object(sunshine, "ensure_package", return_value=True), mock.patch.object(
            sunshine, "pacman_is_installed", return_value=False
        ), mock.patch.object(sunshine, "reload_udev") as reload:
            self.assertTrue(sunshine.install_sunshine())
        reload.assert_called_once()

    def test_firewall_rules_are_scoped_to_allow_from(self):
        with mock.patch.object(sunshine, "ufw_allow", return_value=True) as allow:
            self.assertTrue(sunshine.open_firewall("192.168.2.0/24"))
        self.assertEqual(
            [call.kwargs["from_cidr"] for call in allow.call_args_list],
            ["192.168.2.0/24", "192.168.2.0/24"],
        )
        self.assertEqual(
            sorted(call.args[1] for call in allow.call_args_list), ["tcp", "udp"]
        )


if __name__ == "__main__":
    unittest.main()
