import importlib.util
import os
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


ssh_installer = load_module("dotfiles_ssh_installer", REPO_ROOT / "ssh" / "install.py")
git_installer = load_module("dotfiles_git_installer", REPO_ROOT / "git" / "install.py")


class SshAgentUnitTests(unittest.TestCase):
    """The agent exists so AI sessions over SSH can sign commits; the
    costly mistakes are shadowing the distro's own unit and writing a
    unit that listens somewhere other than where ssh.sh looks."""

    def setUp(self):
        helpers.set_dry_run(False)

    def run_with(self, tmp, packaged):
        service = Path(tmp) / "ssh-agent.service"
        env_d = Path(tmp) / "20-ssh-agent.conf"
        ok = mock.Mock(returncode=0, stderr="")
        with mock.patch.object(ssh_installer, "IS_LINUX", True), mock.patch.object(
            ssh_installer, "AGENT_SERVICE_PATH", service
        ), mock.patch.object(ssh_installer, "AGENT_ENVIRONMENT_D", env_d), mock.patch.object(
            ssh_installer, "_user_unit_exists", return_value=packaged
        ), mock.patch.object(
            ssh_installer.shutil, "which", side_effect=lambda name: f"/usr/bin/{name}"
        ), mock.patch.object(ssh_installer, "run_cmd", return_value=ok), mock.patch.object(
            ssh_installer, "systemctl_enable", return_value=True
        ) as enable:
            self.assertTrue(ssh_installer.configure_ssh_agent())
        return service, env_d, enable

    def test_prefers_the_packaged_socket_unit(self):
        with tempfile.TemporaryDirectory() as tmp:
            service, env_d, enable = self.run_with(tmp, packaged=True)
            self.assertFalse(service.exists())
            self.assertTrue(env_d.exists())
        enable.assert_called_once_with("ssh-agent.socket", user=True)

    def test_writes_an_equivalent_service_when_none_is_packaged(self):
        with tempfile.TemporaryDirectory() as tmp:
            service, env_d, enable = self.run_with(tmp, packaged=False)
            unit = service.read_text()
            self.assertIn("ExecStart=/usr/bin/ssh-agent -D -a %t/ssh-agent.socket", unit)
            # Where ssh.sh and the environment.d drop-in expect it.
            self.assertIn("SSH_AUTH_SOCK=${XDG_RUNTIME_DIR}/ssh-agent.socket", env_d.read_text())
        enable.assert_called_once_with("ssh-agent.service", user=True)

    def test_is_a_no_op_off_linux(self):
        with mock.patch.object(ssh_installer, "IS_LINUX", False), mock.patch.object(
            ssh_installer, "systemctl_enable"
        ) as enable:
            self.assertTrue(ssh_installer.configure_ssh_agent())
        enable.assert_not_called()


class SshGitPathTests(unittest.TestCase):
    def setUp(self):
        helpers.set_dry_run(False)

    def test_op_write_uses_path_and_explicit_account(self):
        completed = mock.Mock(stdout=b"ssh-ed25519 AAAA key\r\n", returncode=0)
        with mock.patch.object(
            ssh_installer.subprocess, "run", return_value=completed
        ) as run, mock.patch.object(ssh_installer, "write_file") as write:
            ssh_installer.op_write_secret("work", "op://vault/key/public", "/key", mode="0644")

        command = run.call_args.args[0]
        self.assertEqual(command[0], "op")
        self.assertEqual(command[1:4], ["read", "--account", "work"])
        self.assertEqual(command[-1], "op://vault/key/public")
        self.assertNotIn("-o", command)
        # Read through stdout, CRLF normalised, so the same code works when
        # `op` is the Windows op.exe under WSL.
        write.assert_called_once_with("/key", "ssh-ed25519 AAAA key\n", mode=0o644)

    def test_askpass_has_explicit_account_and_repairs_mode_when_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            askpass = Path(tmp) / "askpass.sh"
            with mock.patch.object(ssh_installer, "SSH_ASKPASS_AI_PATH", askpass):
                ssh_installer.write_ai_askpass("op://vault/key/password", "work")
                askpass.chmod(0o644)
                ssh_installer.write_ai_askpass("op://vault/key/password", "work")

            self.assertIn(
                "exec op read --account work op://vault/key/password",
                askpass.read_text(),
            )
            self.assertEqual(askpass.stat().st_mode & 0o777, 0o700)

    def test_generated_git_config_uses_effective_xdg_allowed_signers_path(self):
        machine = {
            "git": {
                "user": {
                    "name": "Test User",
                    "email": "test@example.com",
                    "signingkey": None,
                }
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            xdg = Path(tmp) / "custom-config"
            with (
                mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(xdg)}),
                mock.patch.object(
                    git_installer, "get_machine_config", return_value=(machine, "test")
                ),
            ):
                git_installer.generate_config()

            expected = xdg / "git" / "allowed-signers"
            config = (xdg / "git" / "config").read_text()
            ai_config = (xdg / "git" / "config.ai").read_text()
            self.assertIn(f"allowedSignersFile = {expected}", config)
            self.assertIn(f"allowedSignersFile = {expected}", ai_config)


if __name__ == "__main__":
    unittest.main()
