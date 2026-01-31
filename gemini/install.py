#!/usr/bin/env python3
"""Installation script for Gemini CLI"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import info, success, error, command_exists, brew_install


def main():
    info("Installing Gemini CLI...")

    if command_exists('gemini'):
        success("Gemini CLI already installed")
        return 0

    if brew_install('gemini-cli'):
        success("Gemini CLI installed")
        return 0

    error("Failed to install Gemini CLI")
    return 1


if __name__ == '__main__':
    sys.exit(main())
