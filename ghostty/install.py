#!/usr/bin/env python3
"""Installation script for Ghostty terminal"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import info, success, error, app_exists, brew_install


def main():
    info("Installing Ghostty...")

    if app_exists('Ghostty'):
        success("Ghostty already installed")
        return 0

    if brew_install('ghostty', cask=True):
        success("Ghostty installed")
        return 0

    error("Failed to install Ghostty")
    return 1


if __name__ == '__main__':
    sys.exit(main())
