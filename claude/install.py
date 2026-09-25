#!/usr/bin/env python3
"""Installation script for Claude Code"""

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "script"))
from helpers import (
    IS_MACOS,
    SKILLS_DIR,
    command_exists,
    dry,
    ensure_package,
    error,
    get_machine_config,
    info,
    install_symlinks,
    is_dry_run,
    link_directory,
    npm_global_installed,
    npm_install_global,
    parse_dry_run,
    render_agents_md,
    run_cmd,
    success,
    warn,
)

# claude-history is a TUI for reading past sessions: fuzzy search across
# transcripts, then a scrollable viewer. Terminal scrollback is unreliable
# for this because the TUI redraws progress boxes in place, so the
# scrollback holds the residue rather than the conversation.
CLAUDE_HISTORY_TAP = "raine/claude-history"
CLAUDE_HISTORY_FORMULA = "raine/claude-history/claude-history"
CLAUDE_HISTORY_AUR = "claude-history"


def write_settings(claude_dir, topic_dir):
    """Write ~/.claude/settings.json from the base config plus machine tweaks.

    The base config sets `attribution` to empty strings. JSON takes no
    comments, so the reason lives here: that is the documented off-switch for
    Claude Code's built-in `Co-Authored-By: Claude` trailer. Dropping the key
    does not disable the trailer, it restores the default one, which would
    fight the attribution line in the compiled instructions.
    """
    base_file = topic_dir / "settings.json.base"
    settings_path = claude_dir / "settings.json"

    with open(base_file) as f:
        settings = json.load(f)

    # Route git in Claude sessions to the Claude-specific git config
    # (signs with an on-disk SSH key instead of op-ssh-sign).
    xdg_config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    settings.setdefault("env", {})["GIT_CONFIG_GLOBAL"] = str(
        xdg_config_home / "git" / "config.ai"
    )

    machine_config, hostname = get_machine_config()
    if machine_config.get("claude", {}).get("removeDenyRules"):
        info(f"Removing deny rules for machine: {hostname}")
        settings.get("permissions", {}).pop("deny", None)

    if is_dry_run():
        dry(f"would write {settings_path}")
        return

    # If settings.json is currently a symlink, replace it with a real file
    if settings_path.is_symlink():
        settings_path.unlink()

    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")

    success(f"Wrote: {settings_path}")


def install_mcp_servers(topic_dir):
    """Sync user-scope MCP servers from mcp-servers.json.

    MCP servers do not live in settings.json — Claude Code keeps user-scope
    servers in ~/.claude.json, which it owns and rewrites at runtime. So this
    reads the current state from that file but makes changes through the
    `claude mcp` CLI rather than writing the file directly. A server is only
    removed and re-added when its config actually differs, because a
    remove/add cycle discards any stored OAuth authorization for it.
    """
    source = topic_dir / "mcp-servers.json"
    if not source.exists():
        return

    with open(source) as f:
        wanted = json.load(f).get("mcpServers", {})

    if not command_exists("claude"):
        warn("claude CLI not on PATH; skipping MCP server config")
        return

    config_path = Path.home() / ".claude.json"
    current = {}
    if config_path.exists():
        try:
            with open(config_path) as f:
                current = json.load(f).get("mcpServers", {})
        except (OSError, json.JSONDecodeError):
            warn(f"Could not read {config_path}; treating MCP config as empty")

    for name, config in wanted.items():
        if current.get(name) == config:
            success(f"MCP server already configured: {name}")
            continue

        if is_dry_run():
            dry(f"would configure MCP server {name}")
            continue

        if name in current:
            info(f"Updating MCP server: {name}")
            run_cmd(["claude", "mcp", "remove", "--scope", "user", name], check=False)
        else:
            info(f"Adding MCP server: {name}")

        try:
            run_cmd(
                [
                    "claude",
                    "mcp",
                    "add-json",
                    "--scope",
                    "user",
                    name,
                    json.dumps(config),
                ],
                check=True,
            )
            success(f"MCP server configured: {name}")
        except subprocess.CalledProcessError:
            warn(f"Failed to configure MCP server: {name}")


def install_claude_history():
    """Install the claude-history TUI (Homebrew tap on macOS, AUR on Arch).

    Homebrew refuses to load untrusted third-party taps, so `brew trust`
    is required before installing the formula. Optional on both platforms:
    it is a convenience TUI, not something the rest of the setup needs.
    """
    if command_exists("claude-history"):
        success("claude-history already installed")
        return

    if IS_MACOS and not is_dry_run():
        try:
            run_cmd(["brew", "tap", CLAUDE_HISTORY_TAP])
            run_cmd(["brew", "trust", "--tap", CLAUDE_HISTORY_TAP])
        except subprocess.CalledProcessError:
            warn(f"Failed to tap {CLAUDE_HISTORY_TAP}; skipping claude-history")
            return

    ensure_package(
        "claude-history",
        brew=CLAUDE_HISTORY_FORMULA,
        aur=CLAUDE_HISTORY_AUR,
        command="claude-history",
        optional=True,
    )


def main():
    info("Installing Claude Code...")
    parse_dry_run()
    install_symlinks(Path(__file__).resolve().parent)

    # Ensure ~/.claude directory exists
    claude_dir = Path.home() / ".claude"
    if is_dry_run():
        dry(f"would mkdir {claude_dir}")
    else:
        claude_dir.mkdir(parents=True, exist_ok=True)

    topic_dir = Path(__file__).resolve().parent

    render_agents_md(claude_dir / "CLAUDE.md")
    link_directory(SKILLS_DIR, claude_dir / "skills")

    # Link themes directory (LSD Warm Light/Dark, etc.). Claude Code picks up
    # custom themes from ~/.claude/themes/*.json; activate via /theme.
    themes_src = topic_dir / "themes"
    themes_dst = claude_dir / "themes"
    if themes_src.exists():
        link_directory(themes_src, themes_dst)

    write_settings(claude_dir, topic_dir)

    info("Installing/updating Claude Code via official installer...")
    try:
        run_cmd(
            ["bash", "-c", "curl -fsSL https://claude.ai/install.sh | bash"],
            check=True,
        )
        success("Claude Code installed")
    except subprocess.CalledProcessError:
        error("Failed to install Claude Code")
        return 1

    # ccusage powers the monthly $-spend segment in the status line.
    if npm_global_installed("ccusage"):
        success("ccusage already installed")
    elif npm_install_global("ccusage"):
        success("ccusage installed")
    else:
        warn("Failed to install ccusage; status line cost segment will be hidden")

    install_claude_history()
    install_mcp_servers(topic_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
