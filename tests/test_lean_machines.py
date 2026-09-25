"""Tests for lean machines: the `topics` allowlist, `git.sign` and Rancher settings."""

import importlib.util
import json
import os
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


installer = load_module("dotfiles_lean_installer", REPO_ROOT / "script" / "install.py")
check = load_module("dotfiles_lean_check", REPO_ROOT / "script" / "check.py")
git_installer = load_module("dotfiles_lean_git", REPO_ROOT / "git" / "install.py")
docker_installer = load_module("dotfiles_lean_docker", REPO_ROOT / "docker" / "install.py")


def make_topic(root, name, dependencies=()):
    topic_dir = root / name
    topic_dir.mkdir()
    (topic_dir / "install.py").write_text("")
    if dependencies:
        (topic_dir / "dependencies.txt").write_text("\n".join(dependencies) + "\n")


class TopicAllowlistTests(unittest.TestCase):
    def setUp(self):
        helpers.set_dry_run(False)

    def run_installers(self, root, machine):
        with (
            mock.patch.object(installer, "get_machine_config", return_value=(machine, "lab")),
            mock.patch.object(installer, "run_command") as run,
        ):
            result = installer.run_topic_installers(root, "python3")
        ran = [Path(call.args[0][1]).parent.name for call in run.call_args_list]
        return result, ran

    def test_only_allowlisted_topics_run_and_excluded_dependencies_are_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_topic(root, "claude", ["git", "ssh"])
            make_topic(root, "git")
            make_topic(root, "ssh", ["1password"])
            make_topic(root, "1password")

            result, ran = self.run_installers(root, {"topics": ["git", "claude"]})

        self.assertTrue(result)
        self.assertEqual(ran, ["git", "claude"])

    def test_without_allowlist_every_topic_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_topic(root, "git")
            make_topic(root, "ssh")

            result, ran = self.run_installers(root, {})

        self.assertTrue(result)
        self.assertEqual(sorted(ran), ["git", "ssh"])

    def test_unknown_allowlisted_topic_fails_before_running_anything(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_topic(root, "git")

            result, ran = self.run_installers(root, {"topics": ["git", "gti"]})

        self.assertFalse(result)
        self.assertEqual(ran, [])

    def test_final_topic_outside_allowlist_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_topic(root, "dock")
            machine = {"topics": ["git"]}
            with (
                mock.patch.object(
                    installer, "get_machine_config", return_value=(machine, "lab")
                ),
                mock.patch.object(installer, "run_command") as run,
            ):
                self.assertTrue(installer.run_final_topics(root, "python3"))
            run.assert_not_called()


class LeanMachineValidationTests(unittest.TestCase):
    def test_rejects_unknown_and_duplicate_topics(self):
        errors = check.validate_machine_data(
            {"topics": ["git", "gti", "git", 3]}, "machine.json"
        )
        self.assertIn(
            "machine.json:$.topics[1]: 'gti' is not a topic with an install.py", errors
        )
        self.assertIn("machine.json:$.topics[2]: duplicate topic 'git'", errors)
        self.assertIn("machine.json:$.topics[3]: must be a string", errors)

    def test_rejects_non_boolean_git_sign(self):
        errors = check.validate_machine_data({"git": {"sign": "no"}}, "machine.json")
        self.assertIn("machine.json:$.git.sign: must be a boolean", errors)

    def test_rejects_bad_docker_settings(self):
        errors = check.validate_machine_data(
            {"docker": {"vmMemoryGB": 0, "kubernetes": "off", "cpus": 2}},
            "machine.json",
        )
        self.assertIn("machine.json:$.docker.vmMemoryGB: must be a positive integer", errors)
        self.assertIn("machine.json:$.docker.kubernetes: must be a boolean", errors)
        self.assertIn("machine.json:$.docker.cpus: unknown key", errors)


class GitSignTests(unittest.TestCase):
    def render(self, git):
        machine = {
            "git": {
                **git,
                "user": {"name": "Bot", "email": "bot@example.com", "signingkey": None},
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            xdg = Path(tmp)
            with (
                mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(xdg)}),
                mock.patch.object(
                    git_installer, "get_machine_config", return_value=(machine, "test")
                ),
            ):
                git_installer.generate_config()
            return [(xdg / "git" / name).read_text() for name in ("config", "config.ai")]

    def test_signing_is_on_by_default(self):
        for content in self.render({}):
            self.assertIn("gpgsign = true", content)

    def test_sign_false_disables_signing_in_both_configs(self):
        for content in self.render({"sign": False}):
            self.assertIn("gpgsign = false", content)
            self.assertNotIn("gpgsign = true", content)


class RancherSettingsTests(unittest.TestCase):
    def setUp(self):
        helpers.set_dry_run(False)
        self.machine = {"docker": {"vmMemoryGB": 4, "kubernetes": False}}

    def configure(self, machine, rdctl_results, rdctl_exists=True):
        with tempfile.TemporaryDirectory() as tmp:
            rdctl = Path(tmp) / "rdctl"
            if rdctl_exists:
                rdctl.write_text("")
            with (
                mock.patch.object(
                    docker_installer, "get_machine_config", return_value=(machine, "lab")
                ),
                mock.patch.object(docker_installer, "RDCTL", rdctl),
                mock.patch.object(
                    docker_installer, "run_cmd", side_effect=rdctl_results
                ) as run,
            ):
                result = docker_installer.configure_rancher()
            return result, [call.args[0][1:] for call in run.call_args_list]

    @staticmethod
    def settings(memory, kubernetes, engine="moby"):
        return subprocess.CompletedProcess(
            [],
            0,
            stdout=json.dumps(
                {
                    "version": 19,
                    "containerEngine": {"name": engine},
                    "virtualMachine": {"memoryInGB": memory},
                    "kubernetes": {"enabled": kubernetes},
                }
            ),
            stderr="",
        )

    def test_sets_only_the_settings_that_differ(self):
        done = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        result, calls = self.configure(self.machine, [self.settings(6, False), done])

        self.assertTrue(result)
        self.assertEqual(
            calls,
            [["list-settings"], ["set", "--virtual-machine.memory-in-gb=4"]],
        )

    def test_matching_settings_are_left_alone(self):
        result, calls = self.configure(self.machine, [self.settings(4, False)])

        self.assertTrue(result)
        self.assertEqual(calls, [["list-settings"]])

    def test_pins_moby_engine_and_kubernetes_flag_format(self):
        done = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        result, calls = self.configure(
            self.machine, [self.settings(4, True, engine="containerd"), done]
        )

        self.assertTrue(result)
        self.assertEqual(
            calls[1],
            ["set", "--container-engine.name=moby", "--kubernetes.enabled=false"],
        )

    def test_not_running_is_a_warning_not_a_failure(self):
        down = subprocess.CompletedProcess([], 1, stdout="", stderr="connection refused")
        result, calls = self.configure(self.machine, [down])

        self.assertTrue(result)
        self.assertEqual(calls, [["list-settings"]])

    def test_machine_without_docker_settings_does_nothing(self):
        result, calls = self.configure({}, [])

        self.assertTrue(result)
        self.assertEqual(calls, [])

    def test_failed_set_fails_the_topic(self):
        failed = subprocess.CompletedProcess([], 1, stdout="", stderr="boom")
        result, _ = self.configure(self.machine, [self.settings(6, False), failed])

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
