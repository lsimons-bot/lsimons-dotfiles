#!/usr/bin/env python3
"""Installation script for openspec"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import (
    brew_is_installed,
    command_exists,
    error,
    info,
    is_dry_run,
    npm_global_installed,
    parse_dry_run,
    run_cmd,
    success,
    warn,
)

NPM_PACKAGE = '@fission-ai/openspec'


def uninstall_brew_openspec():
    """Remove the legacy Homebrew openspec so the npm-managed copy wins on PATH."""
    if not brew_is_installed('openspec'):
        return
    info("Removing legacy Homebrew openspec...")
    try:
        run_cmd(['brew', 'uninstall', 'openspec'], check=True)
        success("Uninstalled brew openspec")
    except subprocess.CalledProcessError:
        warn("Failed to uninstall brew openspec; continuing")


def main():
    parse_dry_run()
    info("Installing openspec...")

    uninstall_brew_openspec()

    if not command_exists('npm') and not is_dry_run():
        error("npm not found; run node/install.py first")
        return 1

    if npm_global_installed(NPM_PACKAGE):
        success("openspec already installed")
        return 0

    try:
        run_cmd(['npm', 'install', '-g', NPM_PACKAGE], check=True)
    except subprocess.CalledProcessError:
        error(f"Failed to install {NPM_PACKAGE} via npm")
        return 1

    success("openspec installed")
    return 0


if __name__ == '__main__':
    sys.exit(main())
