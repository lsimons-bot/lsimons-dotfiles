#!/usr/bin/env python3
"""Installation script for OpenCode"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "script"))
from helpers import (
    brew_install,
    brew_is_installed,
    error,
    info,
    is_dry_run,
    link_file,
    parse_dry_run,
    success,
)


def install_opencode():
    """Install OpenCode via the anomalyco Homebrew tap."""
    formula = "anomalyco/tap/opencode"
    info("Installing OpenCode...")

    if brew_is_installed(formula):
        success("OpenCode already installed")
        return 0

    if brew_install(formula):
        success("OpenCode installed")
        return 0

    error("Failed to install OpenCode")
    return 1


def configure_opencode():
    """Configure global AGENTS.md symlink."""
    home = Path.home()
    xdg_config_home = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    dotfiles = home / ".dotfiles"
    opencode_dir = xdg_config_home / "opencode"
    agents_md = opencode_dir / "AGENTS.md"
    claude_md_source = dotfiles / "claude" / "CLAUDE.md.symlink"

    if not is_dry_run():
        opencode_dir.mkdir(parents=True, exist_ok=True)

    link_file(claude_md_source, agents_md)


def main():
    parse_dry_run()
    info("Setting up OpenCode...")

    result = install_opencode()
    if result != 0:
        return result

    configure_opencode()
    return 0


if __name__ == "__main__":
    sys.exit(main())
