#!/usr/bin/env python3
"""Installation script for the CLI toolbelt.

General-purpose command-line tools that coding agents (and humans) reach
for: fast search, structured data slicing, shell linting, benchmarking,
document rendering.

They are developer tooling, so they come from mise (`mise use -g`), which
keeps one way of pinning and upgrading them across platforms. socat (no
mise package) and tokei (whose recent releases ship no binaries, so mise
would compile it with cargo) come from the platform's package manager.

A tool that already runs is left alone, so a version pinned by hand in the
global mise config is never overwritten. "Runs" means `<tool> --version`
succeeds: a mise shim for a tool with no active version is on PATH but
fails, and must not count as installed.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import (
    command_exists,
    ensure_package,
    error,
    info,
    is_dry_run,
    mise_use,
    parse_dry_run,
    success,
)

# (command on PATH, mise tool spec)
MISE_TOOLS = [
    ('rg', 'ripgrep'),
    ('fd', 'fd'),
    ('bat', 'bat'),
    ('yq', 'yq'),
    ('ast-grep', 'ast-grep'),
    ('shellcheck', 'shellcheck'),
    ('shfmt', 'shfmt'),
    ('hyperfine', 'hyperfine'),
    ('typst', 'typst'),
    ('pandoc', 'pandoc'),
    ('cloudflared', 'cloudflared'),
    ('age', 'age'),
]


def tool_runs(command):
    """True when `command --version` exits 0 (see the module docstring)."""
    if not command_exists(command):
        return False
    try:
        result = subprocess.run([command, '--version'], capture_output=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def main():
    parse_dry_run()
    info("Installing the CLI toolbelt...")

    if not command_exists('mise') and not is_dry_run():
        error("mise not found; install the 'mise' topic first")
        return 1

    failed = []
    for command, spec in MISE_TOOLS:
        if not is_dry_run() and tool_runs(command):
            success(f"{command} already installed")
            continue
        if mise_use(spec):
            success(f"{command} installed (mise {spec})")
        else:
            error(f"Failed to install {command} via 'mise use -g {spec}'")
            failed.append(command)

    if not ensure_package('socat', brew='socat', pacman='socat', apt='socat', command='socat'):
        failed.append('socat')
    if not ensure_package('tokei', brew='tokei', pacman='tokei', apt='tokei', command='tokei'):
        failed.append('tokei')

    if failed:
        error(f"toolbelt: failed to install {', '.join(failed)}")
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
