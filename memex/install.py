#!/usr/bin/env python3
"""Installation script for memex (https://github.com/nicosuave/memex)

Local transcript search across every coding agent on this machine (Claude
Code, Codex, Cursor, OpenCode, Pi, OpenClaw, Copilot CLI), plus a herdr
plugin that turns its TUI into a session desk.

Indexing is deliberately left to the herdr plugin's session-start hook
rather than the launchd index-service: `index_on_startup` defaults to true
in the plugin, so every herdr session kicks off a background incremental
index. Run `memex index-service enable` by hand if a always-on daemon is
ever wanted instead.

The memex-search and instruction-improver skills are vendored in the
lsimons-skills repository (see `agents/README.md`), not installed by
`memex setup`, which prompts for a TTY.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "script"))
from helpers import (
    brew_install,
    brew_is_installed,
    command_exists,
    dry,
    error,
    info,
    is_dry_run,
    parse_dry_run,
    run_cmd,
    success,
    warn,
)

TAP = "nicosuave/tap"
FORMULA = "nicosuave/tap/memex"

HERDR_PLUGIN = "nicosuave/memex"
HERDR_PLUGIN_ID = "nicosuave.memex"


def install_memex():
    """Install the memex CLI from its Homebrew tap."""
    if brew_is_installed(FORMULA):
        success("memex already installed")
        return True

    try:
        run_cmd(["brew", "tap", TAP])
        run_cmd(["brew", "trust", "--tap", TAP])
    except subprocess.CalledProcessError:
        error(f"Failed to tap {TAP}")
        return False

    if brew_install(FORMULA):
        success("memex installed")
        return True

    error("Failed to install memex")
    return False


def herdr_plugin_installed():
    """Check whether the memex herdr plugin is already registered."""
    result = run_cmd(["herdr", "plugin", "list"], check=False, capture_output=True)
    if result.returncode != 0:
        return False
    return HERDR_PLUGIN_ID in (result.stdout or "")


def install_herdr_plugin():
    """Register memex as a herdr plugin.

    `herdr plugin install` re-downloads the release tarball every run, so
    guard on the plugin list to keep repeat installs cheap.
    """
    if not command_exists("herdr"):
        info("herdr not installed; skipping the memex herdr plugin")
        return

    if is_dry_run():
        dry(f"would install herdr plugin {HERDR_PLUGIN} if absent")
        return

    if herdr_plugin_installed():
        success("memex herdr plugin already installed")
        return

    result = run_cmd(
        ["herdr", "plugin", "install", HERDR_PLUGIN, "--yes"], check=False
    )
    if result.returncode == 0:
        success("memex herdr plugin installed")
    else:
        warn("Failed to install the memex herdr plugin")


def main():
    parse_dry_run()
    info("Installing memex...")

    if not install_memex():
        return 1

    install_herdr_plugin()
    return 0


if __name__ == "__main__":
    sys.exit(main())
