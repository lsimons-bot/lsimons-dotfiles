#!/usr/bin/env python3
"""Installation script for pi-coding-agent"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import (
    command_exists,
    dry,
    error,
    info,
    is_dry_run,
    link_file,
    npm_install_global,
    parse_dry_run,
    success,
    write_file,
)


def install_npm_package():
    """Install the pi-coding-agent npm package via mise-managed npm."""
    info("Installing pi-coding-agent npm package...")

    if command_exists('pi'):
        success("pi-coding-agent already installed")
        return 0

    if npm_install_global('@mariozechner/pi-coding-agent'):
        success("pi-coding-agent installed")
        return 0

    error("Failed to install pi-coding-agent")
    return 1


def configure_agent():
    """Configure AGENTS.md symlink and settings.json"""
    home = Path.home()
    dotfiles = home / '.dotfiles'
    pi_agent_dir = home / '.pi' / 'agent'
    agents_md = pi_agent_dir / 'AGENTS.md'
    settings_json = pi_agent_dir / 'settings.json'
    claude_md_source = dotfiles / 'claude' / 'CLAUDE.md.symlink'

    if not is_dry_run():
        pi_agent_dir.mkdir(parents=True, exist_ok=True)

    link_file(claude_md_source, agents_md)

    # Configure non-volatile settings in settings.json (preserves lastChangelogVersion)
    default_settings = {
        "defaultProvider": "github-copilot",
        "defaultModel": "gemini-3-flash-preview",
        "defaultThinkingLevel": "off",
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
