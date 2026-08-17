import importlib.util
import json
import shlex
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DeterministicAgentIntegrationTests(unittest.TestCase):
    def test_opencode_defaults_include_provider(self):
        config = json.loads((REPO_ROOT / "opencode/opencode.json.symlink").read_text())
        self.assertEqual(config["model"], "litelm/azure/gpt-5-6-sol")
        self.assertEqual(config["small_model"], "litelm/azure/gpt-5-6-luna")

    def test_pi_shell_prefix_uses_shell_quoting(self):
        module = load_module(
            "pi_install_test", REPO_ROOT / "pi-coding-agent/install.py"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            config_home = home / "config with $variables"
            with (
                patch.object(module.Path, "home", return_value=home),
                patch.dict(module.os.environ, {"XDG_CONFIG_HOME": str(config_home)}),
                patch.object(module, "is_dry_run", return_value=False),
                patch.object(module, "render_agents_md"),
                patch.object(module, "link_directory"),
                patch.object(module, "write_file") as write_file,
                patch.object(module, "success"),
            ):
                module.configure_agent()

            settings = json.loads(write_file.call_args.args[1])
            expected = "export GIT_CONFIG_GLOBAL=" + shlex.quote(
                str(config_home / "git/config.ai")
            )
            self.assertEqual(settings["shellCommandPrefix"], expected)

    def test_claude_settings_leave_attribution_unset(self):
        """Claude gets the attribution line from its instructions, not settings."""
        module = load_module("claude_install_test", REPO_ROOT / "claude/install.py")
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_dir = Path(tmpdir)
            with (
                patch.object(module, "get_machine_config", return_value=({}, "test")),
                patch.object(module, "is_dry_run", return_value=False),
                patch.object(module, "info"),
                patch.object(module, "success"),
            ):
                module.write_settings(claude_dir, REPO_ROOT / "claude")

            settings = json.loads((claude_dir / "settings.json").read_text())
            self.assertNotIn("attribution", settings)

    def test_claude_instructions_carry_the_literal_attribution_line(self):
        module = load_module("agents_shared_test", REPO_ROOT / "agents/shared.py")
        rendered = module.render_instructions(None)
        self.assertIn("Co-Authored-By: lsimons-bot <bot@leosimons.com>", rendered)
        self.assertNotIn("attribution:start", rendered)

    def test_history_rewrites_are_governed_by_instructions_not_deny_rules(self):
        instructions = (REPO_ROOT / "agents/AGENTS.md").read_text()
        self.assertIn("## Preserving History", instructions)
        deny = json.loads((REPO_ROOT / "claude/settings.json.base").read_text())[
            "permissions"
        ]["deny"]
        for rule in deny:
            self.assertNotIn("--amend", rule)
            self.assertNotIn("--force", rule)
            self.assertNotIn("--delete", rule)

    def test_windows_installer_uses_shared_agent_sources(self):
        installer = (REPO_ROOT / "windows/install-claude-settings.ps1").read_text()
        self.assertIn("Join-Path $agentsDir 'AGENTS.md'", installer)
        self.assertIn("'lsimons-skills' 'skills'", installer)
        self.assertNotIn("CLAUDE.md.symlink", installer)
        self.assertIn("attribution:start", installer)
        self.assertNotIn("$settings['attribution']", installer)

    def test_gemini_routes_git_through_ai_config(self):
        shell_config = (REPO_ROOT / "gemini/gemini.sh").read_text()
        self.assertIn("GIT_CONFIG_GLOBAL=", shell_config)
        self.assertIn("/git/config.ai", shell_config)

    def test_agents_using_ai_git_config_depend_on_git_and_ssh(self):
        topics = (
            "codex",
            "opencode",
            "pi-coding-agent",
            "copilot",
            "claude",
            "gemini",
        )
        for topic in topics:
            dependencies = set(
                (REPO_ROOT / topic / "dependencies.txt").read_text().splitlines()
            )
            self.assertTrue({"git", "ssh"} <= dependencies, topic)

    def test_installer_runtime_dependencies_are_explicit(self):
        claude_dependencies = set(
            (REPO_ROOT / "claude/dependencies.txt").read_text().splitlines()
        )
        ssh_dependencies = set(
            (REPO_ROOT / "ssh/dependencies.txt").read_text().splitlines()
        )
        self.assertTrue({"jq", "node"} <= claude_dependencies)
        self.assertIn("1password", ssh_dependencies)

    def test_agents_topic_needs_node_for_the_agent_browser_cli(self):
        dependencies = set(
            (REPO_ROOT / "agents/dependencies.txt").read_text().splitlines()
        )
        self.assertIn("node", dependencies)

    def test_skills_come_from_the_sibling_lsimons_skills_checkout(self):
        module = load_module("agents_shared_test", REPO_ROOT / "agents/shared.py")
        self.assertEqual(
            module.SKILLS_DIR, REPO_ROOT.parent / "lsimons-skills" / "skills"
        )
        self.assertFalse((REPO_ROOT / "agents/skills").exists())


if __name__ == "__main__":
    unittest.main()
