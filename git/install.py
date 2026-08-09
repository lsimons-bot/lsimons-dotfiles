#!/usr/bin/env python3
"""Installation script for Git"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "script"))
from helpers import (
    AI_KEY_PUB_PATH,
    SSH_CONFIG_AI_PATH,
    backup_file,
    brew_install,
    brew_is_installed,
    error,
    find_ssh_key,
    get_machine_config,
    info,
    is_dry_run,
    parse_dry_run,
    run_cmd,
    success,
    warn,
    write_file,
)

GPG_SSH_PROGRAM_DEFAULT = "/Applications/1Password.app/Contents/MacOS/op-ssh-sign"


def _xdg_git_dir():
    home = Path.home()
    xdg = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    return xdg / "git"


def _render_config(template, **values):
    """Substitute placeholders in the config template.

    Trailing whitespace differs between the template and what we want
    to compare against later, so we normalise via .format() only.
    """
    return template.format(**values)


def _write_real_file(path, content):
    """Write content to path, replacing a symlink if one is there.

    The repo previously symlinked ~/.config/git/config to a tracked file;
    after migrating to a generated config we want a real file at that
    path so writes don't follow the symlink back into the repo.
    """
    path = Path(path)
    if path.is_symlink():
        if is_dry_run():
            info(f"would unlink symlink at {path}")
        else:
            path.unlink()
    if path.exists() and path.read_text() == content:
        return False
    write_file(path, content)
    return True


def migrate_legacy_files():
    """Move aside files left over from the include-based config layout.

    - ~/.gitconfig: settings have been folded into ~/.config/git/config,
      so back it up. Git reads both locations; leaving the file in place
      would silently shadow our generated config.
    - ~/.config/git/config.local: previously held per-machine user info
      that's now baked directly into ~/.config/git/config. Remove it.
    """
    home = Path.home()
    legacy = [
        home / ".gitconfig",
        _xdg_git_dir() / "config.local",
    ]
    for path in legacy:
        if not (path.exists() or path.is_symlink()):
            continue
        if is_dry_run():
            info(f"would back up legacy {path}")
            continue
        backup_file(path)
        success(f"Backed up legacy {path}")


def generate_config():
    """Write ~/.config/git/config and ~/.config/git/config.ai.

    Both files are produced from git/config.template with different
    substitutions: the regular config uses the machine's primary
    signing key and op-ssh-sign; the AI variant uses the on-disk
    SSH key and ssh-keygen so commits work inside sandboxes
    without 1Password prompts.
    """
    template_path = Path(__file__).resolve().parent / "config.template"
    template = template_path.read_text()

    machine_config, hostname = get_machine_config()
    git_user = machine_config["git"]["user"]
    signing_key = git_user["signingkey"]
    signing_key_pub = ""
    if signing_key is not None:
        ssh_key = find_ssh_key(signing_key)
        if ssh_key is None:
            warn(f"signing key {signing_key} not found in config")
        else:
            signing_key_pub = ssh_key["public_key"]

    config_path = _xdg_git_dir() / "config"
    ai_path = _xdg_git_dir() / "config.ai"

    main_content = _render_config(
        template,
        allowed_signers_file=str(_xdg_git_dir() / "allowed-signers"),
        name=git_user["name"],
        email=git_user["email"],
        signingkey=signing_key_pub,
        gpg_ssh_program=GPG_SSH_PROGRAM_DEFAULT,
        editor="zed --wait",
        ssh_command_block="",
    )
    ai_content = _render_config(
        template,
        allowed_signers_file=str(_xdg_git_dir() / "allowed-signers"),
        name=git_user["name"],
        email=git_user["email"],
        signingkey=str(AI_KEY_PUB_PATH),
        gpg_ssh_program="ssh-keygen",
        editor="vim",
        ssh_command_block=f"\tsshCommand = ssh -F {SSH_CONFIG_AI_PATH}\n",
    )

    if _write_real_file(config_path, main_content):
        success(f"Generated {config_path} for {hostname}")
    else:
        success(f"Git config already up to date ({git_user['name']})")

    if _write_real_file(ai_path, ai_content):
        success(f"Generated {ai_path}")
    else:
        success(f"Git {ai_path} already up to date")


def generate_allowed_signers():
    """Regenerate ~/.config/git/allowed-signers from known signing keys.

    Assembles entries from the machine's primary signing key (machine
    config) and the Claude signing key if present. Both map to the
    user's git email as principal. This file is needed for
    `git log --show-signature` (and git verify-commit) to verify SSH
    signatures without the "gpg.ssh.allowedSignersFile needs to be
    configured" error.

    Takes ownership of the file — manual additions (e.g. collaborator
    keys) will be overwritten.
    """
    allowed_signers = _xdg_git_dir() / "allowed-signers"

    machine_config, _ = get_machine_config()
    git_user = machine_config["git"]["user"]
    email = git_user["email"]

    entries = set()

    ssh_keys = machine_config.get("ssh", {}).get("keys", [])
    for ssh_key in ssh_keys:
        sign = ssh_key.get("sign", False)
        if not sign:
            continue
        public_key = ssh_key["public_key"]
        entries.add(f"{email} {public_key}")

    content = "# Generated by git/install.py — do not edit by hand\n"
    content += "\n".join(sorted(entries)) + "\n" if entries else ""

    if allowed_signers.exists() and allowed_signers.read_text() == content:
        success("Git allowed-signers already up to date")
    else:
        write_file(allowed_signers, content)
        success(f"Generated {allowed_signers} ({len(entries)} key(s))")


def main():
    parse_dry_run()

    info("Installing Git...")

    migrate_legacy_files()
    generate_config()
    generate_allowed_signers()

    if brew_is_installed("git"):
        success("Git already installed")
    elif brew_install("git"):
        success("Git installed")
    else:
        error("Failed to install Git")
        return 1

    if brew_is_installed("git-credential-manager"):
        success("Git Credential Manager already installed")
    elif brew_install("git-credential-manager", cask=True):
        success("Git Credential Manager installed")
    else:
        error("Failed to install Git Credential Manager")
        return 1

    if brew_is_installed("git-filter-repo"):
        success("git-filter-repo already installed")
    elif brew_install("git-filter-repo"):
        success("git-filter-repo installed")
    else:
        error("Failed to install git-filter-repo")
        return 1

    lfs_already_installed = brew_is_installed("git-lfs")
    if lfs_already_installed:
        success("git-lfs already installed")
    elif brew_install("git-lfs"):
        success("git-lfs installed")
    else:
        error("Failed to install git-lfs")
        return 1

    # config.template already hardcodes the filter.lfs.* config this sets, so
    # it's idempotent, but git-lfs still expects this init step to run.
    result = run_cmd(
        ["git", "lfs", "install", "--skip-repo"], check=False, capture_output=True
    )
    if result.returncode != 0:
        error(f"Failed to initialize git-lfs: {result.stderr.strip()}")
        return 1
    if lfs_already_installed:
        success("git-lfs already initialized")
    else:
        success("git-lfs initialized")

    return 0


if __name__ == "__main__":
    sys.exit(main())
