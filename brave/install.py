#!/usr/bin/env python3
"""Installation script for Brave Browser"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import info, success, error, app_exists, brew_install


def main():
    info("Installing Brave Browser...")

    if app_exists('Brave Browser'):
        success("Brave Browser already installed")
        return 0

    if brew_install('brave-browser', cask=True):
        success("Brave Browser installed")
        return 0

    error("Failed to install Brave Browser")
    return 1


if __name__ == '__main__':
    sys.exit(main())
