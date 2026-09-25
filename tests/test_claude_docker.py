"""Tests for the opt-in claude-docker topic and the `claude.docker` key
that gates it.

The costly mistakes are cloning and building a multi-GB image on a machine
that never asked for it, a typo in the machine config silently disabling
the gate, and host-only settings (the sandbox block, hooks with host paths)
leaking into the container's settings.json.
"""

import importlib.util
import json
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
        self.assertNotIn("hooks", settings)
        self.assertIs(settings["autoUpdates"], False)

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


if __name__ == "__main__":
    unittest.main()
