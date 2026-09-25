#!/usr/bin/env python3
"""Installation script for pi-coding-agent"""

import json
import os
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import (
    SKILLS_DIR,
    dry,
    error,
    info,
    is_dry_run,
    link_directory,
    npm_global_installed,
    npm_install_global,
    parse_dry_run,
    render_agents_md,
    success,
    write_file,
)


def install_npm_package():
    """Install the pi-coding-agent npm package via mise-managed npm."""
    info("Installing pi-coding-agent npm package...")

    if npm_global_installed('@mariozechner/pi-coding-agent'):
        success("pi-coding-agent already installed")
        return 0

    if npm_install_global('@mariozechner/pi-coding-agent'):
        success("pi-coding-agent installed")
        return 0

    error("Failed to install pi-coding-agent")
    return 1


def configure_agent():
    """Configure AGENTS.md symlink, themes, and settings.json"""
    home = Path.home()
    topic_dir = Path(__file__).resolve().parent
    pi_agent_dir = home / '.pi' / 'agent'
    agents_md = pi_agent_dir / 'AGENTS.md'
    settings_json = pi_agent_dir / 'settings.json'

    if not is_dry_run():
        pi_agent_dir.mkdir(parents=True, exist_ok=True)

    render_agents_md(agents_md)

    # Link custom LSD warm themes (mirrors the Claude Code themes). Pi picks
    # these up from ~/.pi/agent/themes/*.json; activate via /settings.
    themes_src = topic_dir / 'themes'
    if themes_src.exists():
        link_directory(themes_src, pi_agent_dir / 'themes')

    # Route git in pi sessions to the AI-specific git config (signs with an
    # on-disk SSH key instead of op-ssh-sign, so no 1Password prompt mid-
    # session). Matches the Claude Code and Codex topics. Pi has no env block,
    # so export it via shellCommandPrefix, which runs before every bash command.
    xdg_config_home = Path(os.environ.get('XDG_CONFIG_HOME', home / '.config'))
    git_config_ai = xdg_config_home / 'git' / 'config.ai'
    shell_command_prefix = f'export GIT_CONFIG_GLOBAL={shlex.quote(str(git_config_ai))}'

    # Configure non-volatile settings in settings.json (preserves lastChangelogVersion)
    default_settings = {
        "defaultProvider": "github-copilot",
        "defaultModel": "claude-opus-4.8",
        "defaultThinkingLevel": "low",
        "theme": "lsd-warm-light",
        "shellCommandPrefix": shell_command_prefix,
        # Load the shared skills dir (same skills as the claude/codex/copilot/
        # opencode topics) alongside pi's own auto-discovered ~/.pi/agent/skills.
        "skills": [str(SKILLS_DIR)],
    }

    if settings_json.exists():
        with open(settings_json) as f:
            settings = json.load(f)
        updated = False
        for key, value in default_settings.items():
            if settings.get(key) != value:
                settings[key] = value
                updated = True
        if updated:
            content = json.dumps(settings, indent=2) + '\n'
            write_file(settings_json, content)
            success("Updated settings.json with defaults")
        else:
            success("settings.json already has correct defaults")
    else:
        if is_dry_run():
            dry(f"would write {settings_json}")
        else:
            content = json.dumps(default_settings, indent=2) + '\n'
            write_file(settings_json, content)
            success("Created settings.json with defaults")


def main():
    parse_dry_run()
    info("Setting up pi-coding-agent...")

    result = install_npm_package()
    if result != 0:
        return result

    configure_agent()
    return 0


if __name__ == '__main__':
    sys.exit(main())
