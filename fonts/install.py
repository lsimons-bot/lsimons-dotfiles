#!/usr/bin/env python3
"""Installation script for fonts"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "script"))
from helpers import (
    brew_install,
    brew_is_installed,
    error,
    info,
    parse_dry_run,
    success,
)


FONTS = [
    "font-cascadia-code",
    "font-iosevka",
    "font-jetbrains-mono",
    "font-lilex",
    "font-lilex-nerd-font",
]


def main():
    parse_dry_run()
    info("Installing fonts...")

    for font in FONTS:
        if brew_is_installed(font):
            success(f"{font} already installed")
        elif brew_install(font, cask=True):
            success(f"{font} installed")
        else:
            error(f"Failed to install {font}")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
