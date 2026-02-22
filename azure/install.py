#!/usr/bin/env python3
"""Installation script for Azure CLI"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "script"))
from helpers import brew_install, brew_is_installed, error, info, success


def main():
    info("Installing Azure CLI...")

    if brew_is_installed("azure-cli"):
        success("azure-cli already installed")
    else:
        info("Installing azure-cli via Homebrew...")
        if not brew_install("azure-cli"):
            error("Failed to install azure-cli")
            return 1
        success("azure-cli installed")

    return 0


if __name__ == "__main__":
    sys.exit(main())
