#!/usr/bin/env python3
"""Installation script for Quarto."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "script"))
from helpers import brew_install, command_exists, error, info, parse_dry_run, success


def main():
    parse_dry_run()
    info("Installing Quarto...")

    if command_exists("quarto"):
        success("Quarto already installed")
        return 0

    # quarto is a cask whose pkg installer requires sudo; brew will prompt
    # for the password interactively.
    if brew_install("quarto", cask=True):
        success("Quarto installed")
        return 0

    error("Failed to install Quarto")
    return 1


if __name__ == "__main__":
    sys.exit(main())
