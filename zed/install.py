#!/usr/bin/env python3
"""Installation script for Zed editor"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import info, success, error, app_exists, brew_install


def main():
    info("Installing Zed...")

    if app_exists('Zed'):
        success("Zed already installed")
        return 0

    if brew_install('zed', cask=True):
        success("Zed installed")
        return 0

    error("Failed to install Zed")
    return 1


if __name__ == '__main__':
    sys.exit(main())
