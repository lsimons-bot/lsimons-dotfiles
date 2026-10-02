"""Tests for the opt-in claude-docker topic and the `claude.docker` key
that gates it.

The costly mistakes are cloning and building a multi-GB image on a machine
that never asked for it, a typo in the machine config silently disabling
the gate, and host-only settings (the sandbox block, hooks with host paths)
leaking into the container's settings.json.
"""

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "script"))

import check


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


claude_docker = load_module("dotfiles_claude_docker", REPO_ROOT / "claude-docker" / "install.py")


class SchemaTests(unittest.TestCase):
    def test_accepts_boolean_flags(self):
        errors = check.validate_machine_data(
            {"claude": {"docker": True, "removeDenyRules": False}}, "machine.json"
        )
        self.assertEqual(errors, [])

    def test_rejects_stringly_typed_flag_and_unknown_key(self):
        errors = check.validate_machine_data(
            {"claude": {"docker": "yes", "dokcer": True}}, "machine.json"
        )
        self.assertIn("machine.json:$.claude.docker: must be a boolean", errors)
        self.assertIn("machine.json:$.claude.dokcer: unknown key", errors)


class GateTests(unittest.TestCase):
    def test_skips_when_not_enabled(self):
        with mock.patch.object(claude_docker, "parse_dry_run"), mock.patch.object(
            claude_docker, "get_machine_config", return_value=({}, "host")
        ), mock.patch.object(claude_docker, "set_default_marker") as marker, mock.patch.object(
            claude_docker, "clone_repo"
        ) as clone:
            self.assertEqual(claude_docker.main(), 0)
        clone.assert_not_called()
        # Turning claude.docker off must also stop `claude` running claude-docker.
        marker.assert_called_once_with(False)

    def test_truthy_non_boolean_does_not_enable(self):
        config = {"claude": {"docker": "yes"}}
        with mock.patch.object(claude_docker, "get_machine_config", return_value=(config, "host")):
            self.assertFalse(claude_docker.docker_enabled())


class DockerByDefaultTests(unittest.TestCase):
    def test_schema_accepts_it_with_docker(self):
        errors = check.validate_machine_data(
            {"claude": {"docker": True, "dockerByDefault": True}}, "machine.json"
        )
        self.assertEqual(errors, [])

    def test_schema_rejects_it_without_docker(self):
        # `claude` would run a claude-docker that was never installed.
        errors = check.validate_machine_data({"claude": {"dockerByDefault": True}}, "machine.json")
        self.assertIn(
            "machine.json:$.claude.dockerByDefault: requires $.claude.docker to be true", errors
        )

    def test_needs_both_flags(self):
        cases = [
            ({"claude": {"docker": True, "dockerByDefault": True}}, True),
            ({"claude": {"docker": True}}, False),
            ({"claude": {"dockerByDefault": True}}, False),
            ({"claude": {"docker": True, "dockerByDefault": "yes"}}, False),
        ]
        for config, expected in cases:
            with mock.patch.object(
                claude_docker, "get_machine_config", return_value=(config, "host")
            ):
                self.assertIs(claude_docker.docker_by_default(), expected, config)

    def test_marker_is_written_and_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "claude-docker" / "default-claude"
            with mock.patch.object(claude_docker, "DEFAULT_MARKER", marker), mock.patch.object(
                claude_docker, "is_dry_run", return_value=False
            ):
                claude_docker.set_default_marker(True)
                self.assertEqual(marker.read_text(), claude_docker.DEFAULT_MARKER_TEXT)
                claude_docker.set_default_marker(True)
                claude_docker.set_default_marker(False)
                self.assertFalse(marker.exists())
                claude_docker.set_default_marker(False)

    def test_rc_checks_the_marker_the_installer_writes(self):
        rc = (REPO_ROOT / "claude-docker" / "rc.sh").read_text()
        relative = claude_docker.DEFAULT_MARKER.relative_to(claude_docker.XDG_CONFIG_HOME)
        self.assertIn(f'"${{XDG_CONFIG_HOME:-$HOME/.config}}/{relative}"', rc)

    def run_rc(self, shell, with_marker, command):
        """Source rc.sh in `shell` with stub claude/claude-docker on PATH."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            if with_marker:
                (tmp / "claude-docker").mkdir()
                (tmp / "claude-docker" / "default-claude").write_text("")
            bin_dir = tmp / "bin"
            bin_dir.mkdir()
            for name in ("claude", "claude-docker"):
                stub = bin_dir / name
                stub.write_text(f'#!/bin/sh\necho {name} "$@"\n')
                stub.chmod(0o755)
            env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(tmp), "XDG_CONFIG_HOME": str(tmp)}
            script = f". {REPO_ROOT / 'claude-docker' / 'rc.sh'}; {command}"
            result = subprocess.run(
                [shell, "-c", script], capture_output=True, text=True, env=env, check=False
            )
        return result.returncode, result.stdout.strip()

    def test_rc_switches_claude_to_claude_docker(self):
        for shell in ("bash", "zsh"):
            if shutil.which(shell) is None:
                continue
            with self.subTest(shell=shell):
                self.assertEqual(
                    self.run_rc(shell, True, "claude -p hi"),
                    (0, "claude-docker --gh --glab -p hi"),
                )
                self.assertEqual(self.run_rc(shell, True, "claude-local -p hi"), (0, "claude -p hi"))

    def test_rc_leaves_claude_alone_without_the_marker(self):
        for shell in ("bash", "zsh"):
            if shutil.which(shell) is None:
                continue
            with self.subTest(shell=shell):
                self.assertEqual(self.run_rc(shell, False, "claude -p hi"), (0, "claude -p hi"))
                self.assertNotEqual(self.run_rc(shell, False, "claude-local")[0], 0)


class DockerSettingsTests(unittest.TestCase):
    def setUp(self):
        with open(REPO_ROOT / "claude" / "settings.json.base") as f:
            self.base = json.load(f)

    def test_drops_host_only_keys_and_disables_auto_updates(self):
        base = {**self.base, "sandbox": {"network": {}}, "hooks": {"PreToolUse": []}}
        settings = claude_docker.docker_settings(base, {})
        self.assertNotIn("sandbox", settings)
        self.assertEqual(settings["hooks"], claude_docker.CONTAINER_HOOKS)
        self.assertIs(settings["autoUpdates"], False)

    def test_session_start_hook_points_at_a_script_in_the_personal_image(self):
        script = claude_docker.PERSONAL_IMAGE_DIR / Path(claude_docker.SESSION_START_SCRIPT).name
        self.assertTrue(script.is_file(), script)
        dockerfile = (claude_docker.PERSONAL_IMAGE_DIR / "Dockerfile").read_text()
        self.assertIn(f"{script.name} {Path(claude_docker.SESSION_START_SCRIPT).parent}/", dockerfile)

    def test_session_start_hook_is_a_no_op_without_the_script(self):
        # The plain claude-code:local image reads the same settings file.
        command = claude_docker.CONTAINER_HOOKS["SessionStart"][0]["hooks"][0]["command"]
        result = subprocess.run(
            ["sh", "-c", command], capture_output=True, text=True, check=False
        )
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_keeps_the_rest_of_the_base(self):
        # Attribution in particular: dropping it restores Claude's own
        # Co-Authored-By trailer (see claude/install.py write_settings).
        settings = claude_docker.docker_settings(self.base, {})
        for key in self.base.keys() - set(claude_docker.EXCLUDED_KEYS):
            self.assertEqual(settings[key], self.base[key], key)

    def test_does_not_mutate_the_base(self):
        before = json.dumps(self.base, sort_keys=True)
        claude_docker.docker_settings(self.base, {"claude": {"removeDenyRules": True}})
        self.assertEqual(json.dumps(self.base, sort_keys=True), before)

    def test_remove_deny_rules_applies_like_the_host(self):
        settings = claude_docker.docker_settings(self.base, {"claude": {"removeDenyRules": True}})
        self.assertNotIn("deny", settings["permissions"])


class PersonalImageTests(unittest.TestCase):
    def test_wrapper_defaults_to_the_image_the_installer_builds(self):
        # A mismatch would leave the wrapper pointing at an image nothing builds.
        wrapper = claude_docker.WRAPPER.read_text()
        self.assertIn(
            f'CLAUDE_DOCKER_IMAGE="${{CLAUDE_DOCKER_IMAGE:-{claude_docker.PERSONAL_IMAGE}}}"',
            wrapper,
        )

    def test_wrapper_is_not_sourced_by_the_shell_rc_files(self):
        # zshrc/bashrc source every <topic>/*.sh; the wrapper's exec would
        # then replace each new interactive shell with claude-docker.
        sourced = set((REPO_ROOT / "claude-docker").glob("*.sh"))
        self.assertNotIn(claude_docker.WRAPPER, sourced)
        self.assertTrue(claude_docker.WRAPPER.is_file())

    def test_personal_image_builds_on_the_base(self):
        dockerfile = (claude_docker.PERSONAL_IMAGE_DIR / "Dockerfile").read_text()
        self.assertIn(f"FROM {claude_docker.IMAGE}\n", dockerfile)

    def test_builds_the_base_before_the_personal_image(self):
        with mock.patch.object(claude_docker, "parse_dry_run"), mock.patch.object(
            claude_docker, "docker_enabled", return_value=True
        ), mock.patch.object(claude_docker, "docker_by_default", return_value=False), mock.patch.object(
            claude_docker, "set_default_marker"
        ), mock.patch.object(claude_docker, "clone_repo", return_value=True), mock.patch.object(
            claude_docker, "link_file"
        ), mock.patch.object(claude_docker, "write_settings"), mock.patch.object(
            claude_docker, "build_image", return_value=True
        ) as build:
            self.assertEqual(claude_docker.main(), 0)
        self.assertEqual(
            [c.args[0] for c in build.call_args_list],
            [claude_docker.IMAGE, claude_docker.PERSONAL_IMAGE, claude_docker.SYNC_IMAGE],
        )


class SyncTests(unittest.TestCase):
    """claude-docker-sync copies container transcripts to the host.

    The costly mistakes are the script running an image nothing builds,
    container auto-memory reaching host sessions, and a machine without a
    running docker failing a caller that only wanted a best-effort sync.
    """

    def test_script_uses_the_image_the_installer_builds(self):
        script = claude_docker.SYNC_SCRIPT.read_text()
        self.assertIn(f'image="{claude_docker.SYNC_IMAGE}"', script)
        self.assertTrue((claude_docker.SYNC_IMAGE_DIR / "Dockerfile").is_file())

    def test_script_is_not_sourced_by_the_shell_rc_files(self):
        sourced = set((REPO_ROOT / "claude-docker").glob("*.sh"))
        self.assertNotIn(claude_docker.SYNC_SCRIPT, sourced)

    def test_script_skips_memory_and_mounts_the_volume_read_only(self):
        script = claude_docker.SYNC_SCRIPT.read_text()
        self.assertIn("--exclude '/*/memory/'", script)
        self.assertIn('-v "$volume:/src:ro"', script)
        self.assertNotIn("--delete", script)

    def run_sync(self, docker_stub):
        """Run the sync script with PATH holding only `docker_stub`, if any."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            bin_dir = tmp / "bin"
            bin_dir.mkdir()
            if docker_stub is not None:
                stub = bin_dir / "docker"
                stub.write_text(docker_stub)
                stub.chmod(0o755)
            # Only the stub dir and system dirs: a real docker elsewhere on
            # the caller's PATH must not be found.
            env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(tmp)}
            if shutil.which("docker", path=env["PATH"]) and docker_stub is None:
                self.skipTest("a docker in /usr/bin or /bin would be found")
            result = subprocess.run(
                [shutil.which("bash"), str(claude_docker.SYNC_SCRIPT)],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
        return result.returncode, result.stderr

    def test_warns_and_succeeds_without_docker(self):
        code, stderr = self.run_sync(None)
        self.assertEqual(code, 0)
        self.assertIn("warning: docker not on PATH", stderr)

    def test_warns_and_succeeds_when_docker_is_not_running(self):
        code, stderr = self.run_sync("#!/bin/sh\nexit 1\n")
        self.assertEqual(code, 0)
        self.assertIn("warning: docker is not running", stderr)

    def test_fails_when_the_image_is_missing(self):
        # Running but no image is a broken install, not "nothing to sync".
        stub = '#!/bin/sh\n[ "$1" = info ] && exit 0\nexit 1\n'
        code, stderr = self.run_sync(stub)
        self.assertEqual(code, 1)
        self.assertIn("image claude-docker-sync:local is missing", stderr)


if __name__ == "__main__":
    unittest.main()
