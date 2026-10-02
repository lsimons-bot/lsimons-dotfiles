import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar
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
    unit that listens somewhere other than where ssh/rc.sh looks."""

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
            # Where ssh/rc.sh and the environment.d drop-in expect it.
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

    def test_op_write_warns_and_skips_when_op_read_fails(self):
        # Over a plain SSH session there is no desktop app to authorize the
        # read; the install must carry on rather than crash.
        failed = mock.Mock(stdout=b"", stderr=b"authorization prompt dismissed", returncode=1)
        with (
            mock.patch.object(ssh_installer.subprocess, "run", return_value=failed),
            mock.patch.object(ssh_installer, "write_file") as write,
            mock.patch.object(ssh_installer, "warn") as warn,
        ):
            ok = ssh_installer.op_write_secret("work", "op://vault/key/public", "/key")

        self.assertFalse(ok)
        write.assert_not_called()
        self.assertIn("authorization prompt dismissed", warn.call_args.args[0])

    def test_ai_key_is_named_after_the_1password_item(self):
        # A key forwarded from the work machine's agent and the local
        # personal key must not share a filename.
        key, pub = helpers.ai_key_paths("sbp_lsimons_ai_ed25519")
        self.assertEqual(key, helpers.SSH_CONFIG_DIR / "sbp_lsimons_ai_ed25519")
        self.assertEqual(pub, helpers.SSH_CONFIG_DIR / "sbp_lsimons_ai_ed25519.pub")
        legacy, _ = helpers.ai_key_paths(None)
        self.assertEqual(legacy, helpers.SSH_CONFIG_DIR / "ai_ed25519")

    def test_legacy_ai_key_is_renamed_unless_new_name_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            ssh_dir = Path(tmp)
            (ssh_dir / "ai_ed25519").write_text("private")
            (ssh_dir / "ai_ed25519.pub").write_text("legacy pub")
            (ssh_dir / "lsimons_ai_ed25519.pub").write_text("new pub")
            with mock.patch.object(ssh_installer, "SSH_CONFIG_DIR", ssh_dir):
                ssh_installer.migrate_legacy_ai_key(
                    ssh_dir / "lsimons_ai_ed25519", ssh_dir / "lsimons_ai_ed25519.pub"
                )

            self.assertFalse((ssh_dir / "ai_ed25519").exists())
            self.assertEqual((ssh_dir / "lsimons_ai_ed25519").read_text(), "private")
            # An already-exported key under the new name wins.
            self.assertTrue((ssh_dir / "ai_ed25519.pub").exists())
            self.assertEqual((ssh_dir / "lsimons_ai_ed25519.pub").read_text(), "new pub")

    def test_ai_ssh_config_points_at_the_named_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_ai = Path(tmp) / "config.ai"
            with mock.patch.object(ssh_installer, "SSH_CONFIG_AI_PATH", config_ai):
                ssh_installer.write_ai_ssh_config(Path("/home/u/.ssh/lsimons_ai_ed25519"))
            # ssh/rc.sh reads the key path from this line.
            self.assertIn("IdentityFile /home/u/.ssh/lsimons_ai_ed25519\n", config_ai.read_text())

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

    def test_ai_git_config_signs_with_the_machines_ai_key(self):
        machine = {
            "git": {
                "user": {"name": "Test User", "email": "test@example.com", "signingkey": None}
            },
            "ssh": {"aiKey": "lsimons_ai_ed25519"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            xdg = Path(tmp) / "config"
            with (
                mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(xdg)}),
                mock.patch.object(
                    git_installer, "get_machine_config", return_value=(machine, "test")
                ),
            ):
                git_installer.generate_config()

            ai_config = (xdg / "git" / "config.ai").read_text()
            self.assertIn(
                f"signingkey = {helpers.SSH_CONFIG_DIR / 'lsimons_ai_ed25519.pub'}", ai_config
            )


class GitCredentialHelperTests(unittest.TestCase):
    """gh and glab each answer only for their own hosts; GCM is scoped to
    Azure DevOps and, on Linux, must name a credential store or every
    call fails. The expensive mistake is a config that silently has no
    working helper for a host, which is what happened on Arch when GCM
    was the default without a store."""

    MACHINE: ClassVar[dict] = {
        "git": {
            "user": {"name": "Test User", "email": "test@example.com", "signingkey": None}
        }
    }

    def render(self, machine=None, gcm_installed=False, linux=False):
        with (
            mock.patch.object(
                git_installer,
                "command_exists",
                side_effect=lambda cmd: cmd == "git-credential-manager" and gcm_installed,
            ),
            mock.patch.object(git_installer, "IS_LINUX", linux),
        ):
            return git_installer.render_credential_blocks(machine or self.MACHINE)

    def test_gitlab_com_gets_glab_by_default(self):
        blocks = self.render()
        self.assertIn(
            '[credential "https://gitlab.com"]\n\thelper = !glab auth git-credential\n',
            blocks,
        )

    def test_machine_config_lists_its_own_gitlab_hosts(self):
        machine = {"git": {**self.MACHINE["git"], "gitlabHosts": ["gitlab.example.internal"]}}
        blocks = self.render(machine)
        self.assertIn('[credential "https://gitlab.example.internal"]', blocks)
        self.assertNotIn("gitlab.com", blocks)

    def test_azure_devops_uses_gcm_only_when_installed(self):
        without = self.render(gcm_installed=False)
        self.assertIn('[credential "https://dev.azure.com"]\n\tuseHttpPath = true\n', without)
        self.assertNotIn("manager", without)

        with_gcm = self.render(gcm_installed=True)
        self.assertIn("\thelper = manager\n", with_gcm)
        self.assertNotIn("credentialStore", with_gcm)

    def test_gcm_on_linux_names_the_secret_service_store(self):
        blocks = self.render(gcm_installed=True, linux=True)
        azure = blocks[blocks.index('[credential "https://dev.azure.com"]') :]
        self.assertIn("\thelper = manager\n", azure)
        self.assertIn("\tcredentialStore = secretservice\n", azure)

    def test_generated_config_defaults_to_gh_and_scopes_the_rest(self):
        with tempfile.TemporaryDirectory() as tmp:
            xdg = Path(tmp) / "xdg"
            with (
                mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(xdg)}),
                mock.patch.object(
                    git_installer, "get_machine_config", return_value=(self.MACHINE, "test")
                ),
                mock.patch.object(
                    git_installer,
                    "command_exists",
                    side_effect=lambda cmd: cmd == "git-credential-manager",
                ),
                mock.patch.object(git_installer, "IS_LINUX", True),
            ):
                git_installer.generate_config()
            for name in ("config", "config.ai"):
                config = (xdg / "git" / name).read_text()
                head, _, scoped = config.partition('[credential "')
                self.assertIn("[credential]\n\thelper =\n\thelper = !gh auth git-credential\n", head)
                self.assertNotIn("manager", head)
                self.assertIn("gitlab.com", scoped)
                self.assertIn("dev.azure.com", scoped)
                self.assertIn("credentialStore = secretservice", scoped)


if __name__ == "__main__":
    unittest.main()
