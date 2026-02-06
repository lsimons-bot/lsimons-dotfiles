#!/usr/bin/env python3
"""Installation script for pi-coding-agent"""

import json
import subprocess
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import info, success, error, command_exists


def install_npm_package():
    """Install the pi-coding-agent npm package"""
    info("Installing pi-coding-agent npm package...")

    if not command_exists('npm'):
        home = str(Path.home() / '.local/share')
        xdg_data_home = os.environ.get('XDG_DATA_HOME', home)
        nvm_dir = Path(xdg_data_home) / 'nvm'

        if not (nvm_dir / 'nvm.sh').exists():
            error("npm not found. Please install Node.js first (run node/install.py)")
            return 1

    # Check if already installed (via nvm environment)
    check_script = '''
        export NVM_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/nvm"
        [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
        which pi 2>/dev/null
    '''
    result = subprocess.run(['bash', '-c', check_script], capture_output=True)
    if result.returncode == 0:
        success("pi-coding-agent already installed")
        return 0

    try:
        install_script = '''
            export NVM_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/nvm"
            [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
            npm install -g @mariozechner/pi-coding-agent
        '''
        subprocess.run(['bash', '-c', install_script], check=True)
        success("pi-coding-agent installed")
        return 0
    except subprocess.CalledProcessError:
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

    # Ensure ~/.pi/agent exists
    pi_agent_dir.mkdir(parents=True, exist_ok=True)

    # Symlink AGENTS.md -> claude/CLAUDE.md.symlink
    if agents_md.is_symlink():
        current = agents_md.resolve()
        if current == claude_md_source.resolve():
            success("AGENTS.md already linked correctly")
        else:
            info(f"AGENTS.md points to {current}, relinking")
            agents_md.unlink()
            agents_md.symlink_to(claude_md_source)
            success(f"Linked AGENTS.md -> {claude_md_source}")
    elif agents_md.exists():
        info("AGENTS.md exists as regular file, replacing with symlink")
        agents_md.unlink()
        agents_md.symlink_to(claude_md_source)
        success(f"Linked AGENTS.md -> {claude_md_source}")
    else:
        agents_md.symlink_to(claude_md_source)
        success(f"Linked AGENTS.md -> {claude_md_source}")

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
            with open(settings_json, 'w') as f:
                json.dump(settings, f, indent=2)
                f.write('\n')
            success("Updated settings.json with defaults")
        else:
            success("settings.json already has correct defaults")
    else:
        settings = default_settings.copy()
        with open(settings_json, 'w') as f:
            json.dump(settings, f, indent=2)
            f.write('\n')
        success("Created settings.json with defaults")


def main():
    info("Setting up pi-coding-agent...")

    result = install_npm_package()
    if result != 0:
        return result

    configure_agent()
    return 0


if __name__ == '__main__':
    sys.exit(main())
