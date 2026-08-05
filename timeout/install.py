#!/usr/bin/env python3
"""Installation script for timeout (https://github.com/aisk/timeout)"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "script"))
from helpers import (
    brew_install,
    brew_is_installed,
    error,
    info,
    parse_dry_run,
    run_cmd,
    success,
)

TAP = "aisk/tap"
FORMULA = "aisk/tap/timeout"


def add_tap():
    """Tap and trust aisk/tap. Homebrew refuses to load untrusted third-party
    taps, so `brew trust` is required before installing the formula."""
    try:
        run_cmd(["brew", "tap", TAP])
        run_cmd(["brew", "trust", "--tap", TAP])
        return True
    except subprocess.CalledProcessError:
        error(f"Failed to tap {TAP}")
        return False


def main():
    parse_dry_run()
    info("Installing timeout...")

    if brew_is_installed(FORMULA):
        success("timeout already installed")
        return 0

    if not add_tap():
        return 1

    if brew_install(FORMULA):
        success("timeout installed")
        return 0

    error("Failed to install timeout")
    return 1


if __name__ == "__main__":
    sys.exit(main())
