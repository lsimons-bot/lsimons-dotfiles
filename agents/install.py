#!/usr/bin/env python3
"""Installation script for shared coding-agent skills.

Skills themselves are vendored in the sibling `lsimons-skills` checkout.
This script only links that collection into the shared locations read by
agents without a dedicated topic, and installs the CLIs that some of those
skills shell out to.

The per-agent topics (claude, codex, copilot, gemini, opencode,
pi-coding-agent) link the same directory into their own configuration.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "script"))
from helpers import (
    SKILLS_DIR,
    XDG_CONFIG_HOME,
    command_exists,
    info,
    is_dry_run,
    link_directory,
    npm_install_global,
    parse_dry_run,
    run_cmd,
    success,
    warn,
)

# Agents without a dedicated topic (Zed, Cursor, Cline, Warp, Amp, ...)
# read skills from these shared locations instead of an agent-specific
# directory.
UNIVERSAL_SKILL_DIRS = (
    Path.home() / ".agents" / "skills",
    XDG_CONFIG_HOME / "agents" / "skills",
)


def install_agent_browser():
    """Install the CLI that the agent-browser skill drives.

    The skill itself is a discovery stub: it shells out to `agent-browser`,
    which serves version-matched instructions and drives its own Chrome
    build. npm blocks the package's postinstall script by default, so fetch
    the browser explicitly.
    """
    if command_exists("agent-browser"):
        success("agent-browser already installed")
    else:
        info("Installing agent-browser...")
        if not npm_install_global("agent-browser"):
            warn("Failed to install agent-browser; its skill will not work")
            return
        success("agent-browser installed")

    if run_cmd(["agent-browser", "install"], check=False).returncode != 0:
        warn("`agent-browser install` failed; run it by hand to fetch Chrome")


def link_skills():
    """Link the vendored skills collection into the shared locations."""
    if not SKILLS_DIR.is_dir() and not is_dry_run():
        warn(
            f"Skills collection not found at {SKILLS_DIR}; "
            "clone https://github.com/lsimons/lsimons-skills next to this "
            "repository and re-run"
        )
        return False

    for skills_dir in UNIVERSAL_SKILL_DIRS:
        link_directory(SKILLS_DIR, skills_dir)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="preview without changing anything"
    )
    parser.parse_args()
    parse_dry_run()

    info("Setting up shared coding-agent skills...")

    ok = link_skills()
    install_agent_browser()

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
