"""Tests for the opt-in remote-access topics (sshd, wayvnc) and the
`remoteAccess` machine-config block that gates them.

The costly mistakes here are all lock-outs or surprise exposure: turning
off password login before a key is authorized, running the host topics
on a machine that never asked for them, a typo in the machine config
silently disabling the gate, and wayvnc (which has no auth of its own)
listening anywhere but the tailnet. So that is what these cover.
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
wayvnc = load_module("dotfiles_wayvnc", REPO_ROOT / "wayvnc" / "install.py")

KEY_A = "ssh-ed25519 AAAAexampleA a@example"
KEY_B = "ssh-ed25519 AAAAexampleB b@example"


class RemoteAccessSchemaTests(unittest.TestCase):
    def test_accepts_the_snow_shaped_block(self):
        errors = check.validate_machine_data(
            {
                "remoteAccess": {
                    "allowFrom": "192.168.2.0/24",
                    "sshd": True,
                    "wayvnc": True,
                }
            },
            "machine.json",
        )
        self.assertEqual(errors, [])

    def test_rejects_stringly_typed_flags_and_unknown_keys(self):
        errors = check.validate_machine_data(
            {"remoteAccess": {"sshd": "yes", "sunshine": True}}, "machine.json"
        )
        self.assertIn("machine.json:$.remoteAccess.sshd: must be a bool", errors)
        self.assertIn("machine.json:$.remoteAccess.sunshine: unknown key", errors)


class GateTests(unittest.TestCase):
    def test_sshd_skips_when_not_enabled(self):
        with mock.patch.object(sshd, "parse_dry_run"), mock.patch.object(
            sshd, "get_remote_access_config", return_value={}
        ), mock.patch.object(sshd, "install_server") as install:
            self.assertEqual(sshd.main(), 0)
        install.assert_not_called()

    def test_wayvnc_skips_when_not_enabled(self):
        with mock.patch.object(wayvnc, "parse_dry_run"), mock.patch.object(
            wayvnc, "get_remote_access_config", return_value={"sshd": True}
        ), mock.patch.object(wayvnc, "install_wayvnc") as install:
            self.assertEqual(wayvnc.main(), 0)
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


class WayvncTests(unittest.TestCase):
    def test_unit_binds_to_the_tailscale_address_only(self):
        exec_start = next(
            line for line in wayvnc.UNIT.splitlines() if line.startswith("ExecStart=")
        )
        self.assertIn('"$(tailscale ip -4)"', exec_start)
        self.assertIn(str(wayvnc.PORT), exec_start)
        self.assertIn("WantedBy=graphical-session.target", wayvnc.UNIT)

    def test_firewall_rule_is_scoped_to_the_tailnet(self):
        with mock.patch.object(wayvnc, "parse_dry_run"), mock.patch.object(
            wayvnc, "get_remote_access_config", return_value={"wayvnc": True}
        ), mock.patch.object(wayvnc, "IS_ARCH", True), mock.patch.object(
            wayvnc, "install_wayvnc", return_value=True
        ), mock.patch.object(wayvnc, "install_unit", return_value=True), mock.patch.object(
            wayvnc, "systemctl_enable", return_value=True
        ), mock.patch.object(wayvnc, "ufw_allow", return_value=True) as allow:
            self.assertEqual(wayvnc.main(), 0)
        allow.assert_called_once()
        self.assertEqual(allow.call_args.kwargs["from_cidr"], "100.64.0.0/10")
        self.assertEqual(allow.call_args.args[:2], (5900, "tcp"))

    def test_unit_is_rewritten_only_when_it_differs(self):
        helpers.set_dry_run(False)
        with tempfile.TemporaryDirectory() as tmp:
            unit_path = Path(tmp) / "wayvnc.service"
            ok = mock.Mock(returncode=0, stderr="")
            with mock.patch.object(wayvnc, "UNIT_PATH", unit_path), mock.patch.object(
                wayvnc, "run_cmd", return_value=ok
            ) as run:
                self.assertTrue(wayvnc.install_unit())
                self.assertTrue(wayvnc.install_unit())
            self.assertEqual(unit_path.read_text(), wayvnc.UNIT)
        run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
