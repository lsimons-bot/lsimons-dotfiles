#!/usr/bin/env python3
"""Installation script for herdr (https://herdr.dev), a terminal agent multiplexer"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import (
    brew_install,
    brew_is_installed,
    error,
    info,
    install_symlinks,
    parse_dry_run,
    success,
)


def main():
    parse_dry_run()
    info("Installing herdr...")

    if brew_is_installed('herdr'):
        success("herdr already installed")
    elif brew_install('herdr'):
        success("herdr installed")
    else:
        error("Failed to install herdr")
        return 1

    if not install_symlinks(Path(__file__).resolve().parent):
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
