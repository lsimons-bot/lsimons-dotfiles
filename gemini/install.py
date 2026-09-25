#!/usr/bin/env python3
"""Installation script for Gemini CLI"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import (
    SKILLS_DIR,
    brew_is_installed,
    brew_uninstall,
    error,
    info,
    is_dry_run,
    link_directory,
    npm_global_installed,
    npm_install_global,
    parse_dry_run,
    render_agents_md,
    success,
    warn,
)


def configure_gemini():
    home = Path.home()
    gemini_dir = home / '.gemini'
    gemini_md = gemini_dir / 'GEMINI.md'

    if not is_dry_run():
        gemini_dir.mkdir(parents=True, exist_ok=True)

    render_agents_md(gemini_md)
    link_directory(SKILLS_DIR, gemini_dir / 'skills')


def main():
    parse_dry_run()
    info("Installing Gemini CLI...")

    # Migrate away from the Homebrew gemini-cli, which has a hard-coded
    # /opt/homebrew/opt/node shebang that breaks once node is managed by mise.
    if brew_is_installed('gemini-cli'):
        info("Removing Homebrew gemini-cli (replacing with npm install)...")
        if not brew_uninstall('gemini-cli'):
            warn("Failed to uninstall Homebrew gemini-cli; continuing anyway")

    if npm_global_installed('@google/gemini-cli'):
        success("Gemini CLI already installed")
    elif npm_install_global('@google/gemini-cli'):
        success("Gemini CLI installed")
    else:
        error("Failed to install Gemini CLI")
        return 1

    configure_gemini()
    return 0


if __name__ == '__main__':
    sys.exit(main())
