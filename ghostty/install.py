#!/usr/bin/env python3
"""Installation script for Ghostty terminal"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import (
    app_exists,
    brew_install,
    error,
    info,
    install_symlinks,
    parse_dry_run,
    success,
)


def main():
    parse_dry_run()
    info("Installing Ghostty...")

    if app_exists('Ghostty'):
        success("Ghostty already installed")
    elif brew_install('ghostty', cask=True):
        success("Ghostty installed")
    else:
        error("Failed to install Ghostty")
        return 1

    if not install_symlinks(Path(__file__).resolve().parent):
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
