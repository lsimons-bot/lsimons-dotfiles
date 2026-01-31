#!/usr/bin/env python3
"""Installation script for 1Password CLI"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import info, success, error, command_exists, brew_install


def main():
    info("Installing 1Password CLI...")

    if command_exists('op'):
        success("1Password CLI already installed")
        return 0

    if brew_install('1password-cli', cask=True):
        success("1Password CLI installed")
        return 0

    error("Failed to install 1Password CLI")
    return 1


if __name__ == '__main__':
    sys.exit(main())
