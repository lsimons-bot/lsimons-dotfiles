#!/usr/bin/env python3
"""Installation script for fnox (1Password secret injection via mise)

Installed via `mise use -g fnox` per the mise-adoption spec. The mise
registry maps `fnox` to `github:jdx/fnox`, so this pulls a prebuilt
release binary — no Rust toolchain / cargo compile needed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import command_exists, error, info, mise_use, parse_dry_run, success


def main():
    parse_dry_run()
    info("Installing fnox...")

    if not command_exists('mise'):
        error("mise not found; install the 'mise' topic first")
        return 1

    if command_exists('fnox'):
        success("fnox already installed")
        return 0

    if not mise_use('fnox'):
        error("Failed to install fnox via 'mise use -g fnox'")
        return 1

    success("fnox installed")
    return 0


if __name__ == '__main__':
    sys.exit(main())
