#!/usr/bin/env python3
"""Installation script for GitHub CLI"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import info, success, error, command_exists, brew_install


def main():
    info("Installing GitHub CLI...")

    if command_exists('gh'):
        success("GitHub CLI already installed")
        return 0

    if brew_install('gh'):
        success("GitHub CLI installed")
        return 0

    error("Failed to install GitHub CLI")
    return 1


if __name__ == '__main__':
    sys.exit(main())
