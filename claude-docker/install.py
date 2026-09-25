#!/usr/bin/env python3
"""Installation script for claude-docker (https://github.com/schubergphilis/claude-docker)

claude-docker runs Claude Code in a hardened container that forwards the
host's Claude config (CLAUDE.md, skills, themes, statusline) read-only.

Opt-in per machine through `claude.docker` in machines/<hostname>.json:
it needs a running container engine and a ~2.4 GB image, which most
machines, and the AI VMs in particular, do not want.

What it sets up:

* clones the repository to ~/git/sbp/claude-docker, and leaves an existing
  checkout alone (it may be on a feature branch);
* links ~/.local/bin/claude-docker to the checkout's run.sh;
* writes ~/.claude/settings.docker.json, the container's settings.json,
  from the same settings.json.base as the host (see docker_settings);
* builds the claude-code:local image when it is missing and docker is
  running. Rebuilds after a pull or pin change are left to the user.
"""

import copy
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "script"))
from helpers import (
    HOME,
    command_exists,
    dry,
    error,
    get_machine_config,
    info,
    is_dry_run,
    link_file,
    parse_dry_run,
    run_cmd,
    success,
    warn,
)

REPO_URL = "https://github.com/schubergphilis/claude-docker.git"
REPO_DIR = HOME / "git" / "sbp" / "claude-docker"
COMMAND_LINK = HOME / ".local" / "bin" / "claude-docker"
IMAGE = "claude-code:local"

CLAUDE_DIR = HOME / ".claude"
SETTINGS_BASE = Path(__file__).resolve().parent.parent / "claude" / "settings.json.base"
SETTINGS_PATH = CLAUDE_DIR / "settings.docker.json"

# Host settings keys that must not reach the container: `sandbox` configures
# the macOS/bubblewrap sandbox, which the container replaces, and `hooks`
# reference host paths. claude/install.py also adds env.GIT_CONFIG_GLOBAL,
# a host path, but only to the host file, so it never needs removing here.
EXCLUDED_KEYS = ("sandbox", "hooks")


def docker_enabled():
    config, _ = get_machine_config()
    return config.get("claude", {}).get("docker") is True


def docker_settings(base, machine_config):
    """Return the container's settings.json, derived from the host base.

    Built from settings.json.base, not the live ~/.claude/settings.json, so
    settings Claude Code writes in a host session (e.g. a per-model effort
    override) do not leak into the container. The same machine tweaks as
    claude/install.py apply, so both files agree on permissions.

    autoUpdates is off because the image pins Claude Code; an in-container
    update would fight the pin and fail as the non-root session user.
    """
    # Deep copy: dropping deny rules below edits a nested dict.
    settings = {
        key: copy.deepcopy(value) for key, value in base.items() if key not in EXCLUDED_KEYS
    }
    if machine_config.get("claude", {}).get("removeDenyRules"):
        settings.get("permissions", {}).pop("deny", None)
    settings["autoUpdates"] = False
    return settings


def clone_repo():
    if (REPO_DIR / ".git").exists():
        success(f"claude-docker already cloned: {REPO_DIR}")
        return True
    if REPO_DIR.exists():
        error(f"{REPO_DIR} exists but is not a git checkout; move it aside and re-run")
        return False
    if is_dry_run():
        dry(f"would run: git clone {REPO_URL} {REPO_DIR}")
        return True
    REPO_DIR.parent.mkdir(parents=True, exist_ok=True)
    try:
        run_cmd(["git", "clone", REPO_URL, str(REPO_DIR)], check=True)
    except subprocess.CalledProcessError:
        error(f"Failed to clone {REPO_URL}")
        return False
    success(f"Cloned claude-docker to {REPO_DIR}")
    return True


def write_settings():
    with open(SETTINGS_BASE) as f:
        base = json.load(f)
    machine_config, _ = get_machine_config()
    settings = docker_settings(base, machine_config)

    if is_dry_run():
        dry(f"would write {SETTINGS_PATH}")
        return

    if SETTINGS_PATH.is_symlink():
        SETTINGS_PATH.unlink()
    CLAUDE_DIR.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")
    success(f"Wrote: {SETTINGS_PATH}")


def build_image():
    """Build the image once. Returns False only when a build was tried and failed."""
    build_cmd = f"docker build -t {IMAGE} {REPO_DIR}"
    if is_dry_run():
        dry(f"would run: {build_cmd} (only if the image is missing)")
        return True
    if not command_exists("docker"):
        warn(f"docker not on PATH; build the image later with: {build_cmd}")
        return True
    if run_cmd(["docker", "info"], check=False, capture_output=True).returncode != 0:
        warn(f"docker is not running; build the image later with: {build_cmd}")
        return True
    inspect = run_cmd(["docker", "image", "inspect", IMAGE], check=False, capture_output=True)
    if inspect.returncode == 0:
        success(f"Image {IMAGE} already built (rebuild after pulling: {build_cmd})")
        return True

    info(f"Building {IMAGE}; this takes a few minutes...")
    try:
        run_cmd(["docker", "build", "-t", IMAGE, str(REPO_DIR)], check=True)
    except subprocess.CalledProcessError:
        error(f"Failed to build {IMAGE}")
        return False
    success(f"Built {IMAGE}")
    return True


def main():
    parse_dry_run()

    if not docker_enabled():
        info("claude.docker is not enabled for this machine; skipping claude-docker")
        return 0

    info("Installing claude-docker...")
    if not clone_repo():
        return 1
    link_file(REPO_DIR / "run.sh", COMMAND_LINK)
    write_settings()
    if not build_image():
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
