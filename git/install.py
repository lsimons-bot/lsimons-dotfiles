#!/usr/bin/env python3
"""Installation script for Git"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import info, success, error, brew_install, brew_is_installed


def main():
    info("Installing Git...")

    if brew_is_installed('git'):
        success("Git already installed")
        return 0

    if brew_install('git'):
        success("Git installed")
        return 0

    error("Failed to install Git")
    return 1


if __name__ == '__main__':
    sys.exit(main())
