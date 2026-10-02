"""Tests for the opt-in claude-docker topic and the `claude.docker` key
that gates it.

The costly mistakes are cloning and building a multi-GB image on a machine
that never asked for it, a typo in the machine config silently disabling
the gate, and host-only settings (the sandbox block, hooks with host paths)
leaking into the container's settings.json.
"""

import importlib.util
import json
import subprocess
import sys
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
        ), mock.patch.object(claude_docker, "clone_repo") as clone:
            self.assertEqual(claude_docker.main(), 0)
        clone.assert_not_called()

    def test_truthy_non_boolean_does_not_enable(self):
        config = {"claude": {"docker": "yes"}}
        with mock.patch.object(claude_docker, "get_machine_config", return_value=(config, "host")):
            self.assertFalse(claude_docker.docker_enabled())


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
        ), mock.patch.object(claude_docker, "clone_repo", return_value=True), mock.patch.object(
            claude_docker, "link_file"
        ), mock.patch.object(claude_docker, "write_settings"), mock.patch.object(
            claude_docker, "build_image", return_value=True
        ) as build:
            self.assertEqual(claude_docker.main(), 0)
        self.assertEqual(
            [c.args[0] for c in build.call_args_list],
            [claude_docker.IMAGE, claude_docker.PERSONAL_IMAGE],
        )


if __name__ == "__main__":
    unittest.main()
