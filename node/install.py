#!/usr/bin/env python3
"""Install Node.js (via mise) + pnpm (via corepack)."""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import command_exists, error, info, is_dry_run, mise_use, parse_dry_run, success


def main():
    parse_dry_run()
    info("Installing Node.js via mise...")

    if not command_exists('mise'):
        error("mise not found; install the 'mise' topic first")
        return 1

    if not mise_use('node@24'):
        error("Failed to install Node.js via mise")
        return 1

    info("Enabling pnpm via corepack...")
    if is_dry_run():
        info("[dry-run] would run: mise exec -- corepack enable pnpm")
    else:
        try:
            subprocess.run(['mise', 'exec', '--', 'corepack', 'enable', 'pnpm'], check=True)
        except subprocess.CalledProcessError:
            error("Failed to enable pnpm via corepack")
            return 1

    success("Node.js + pnpm installed")
    return 0


if __name__ == '__main__':
    sys.exit(main())
