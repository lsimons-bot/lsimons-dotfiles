#!/usr/bin/env python3
"""Installation script for Git"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "script"))
from helpers import (
    backup_file,
    brew_install,
    brew_is_installed,
    error,
    get_machine_config,
    get_short_hostname,
    info,
    is_dry_run,
    parse_dry_run,
    success,
    warn,
    write_file,
)


GPG_SSH_PROGRAM_DEFAULT = "/Applications/1Password.app/Contents/MacOS/op-ssh-sign"
CLAUDE_SIGNING_KEY = Path.home() / ".ssh" / "claude_signing_ed25519.pub"
CLAUDE_SSH_CONFIG = Path.home() / ".ssh" / "config.claude"


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
    """Write ~/.config/git/config and ~/.config/git/config.claude.

    Both files are produced from git/config.template with different
    substitutions: the regular config uses the machine's primary
    signing key and op-ssh-sign; the Claude variant uses the on-disk
    Claude signing key and ssh-keygen so commits work inside sandboxes
    without 1Password prompts.
    """
    template_path = Path(__file__).resolve().parent / "config.template"
    template = template_path.read_text()

    machine_config, hostname = get_machine_config()
    git_user = machine_config["git"]["user"]

    config_path = _xdg_git_dir() / "config"
    claude_path = _xdg_git_dir() / "config.claude"

    main_content = _render_config(
        template,
        name=git_user["name"],
        email=git_user["email"],
        signingkey=git_user["signingkey"],
        gpg_ssh_program=GPG_SSH_PROGRAM_DEFAULT,
        editor="zed --wait",
        ssh_command_block="",
    )
    claude_content = _render_config(
        template,
        name=git_user["name"],
        email=git_user["email"],
        signingkey=str(CLAUDE_SIGNING_KEY),
        gpg_ssh_program="ssh-keygen",
        editor="vim",
        ssh_command_block=f"\tsshCommand = ssh -F {CLAUDE_SSH_CONFIG}\n",
    )

    if _write_real_file(config_path, main_content):
        success(f"Generated {config_path} for {hostname}")
    else:
        success(f"Git config already up to date ({git_user['name']})")

    if _write_real_file(claude_path, claude_content):
        success(f"Generated {claude_path}")
    else:
        success("Git config.claude already up to date")


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

    # Deduplicate: the Claude key is sometimes a copy of the primary
    # signing key (e.g. when restored from the same 1Password document),
    # in which case both paths produce the same allowed-signers line.
    entries = set()

    primary_pub = Path(git_user["signingkey"]).expanduser()
    if primary_pub.exists():
        entries.add(f"{email} {primary_pub.read_text().strip()}")
    else:
        warn(f"Primary signing key missing: {primary_pub}")

    if CLAUDE_SIGNING_KEY.exists():
        entries.add(f"{email} {CLAUDE_SIGNING_KEY.read_text().strip()}")

    content = "# Generated by git/install.py — do not edit by hand\n"
    content += "\n".join(sorted(entries)) + "\n" if entries else ""

    if allowed_signers.exists() and allowed_signers.read_text() == content:
        success("Git allowed-signers already up to date")
    else:
        write_file(allowed_signers, content)
        success(f"Generated {allowed_signers} ({len(entries)} key(s))")


def warn_if_claude_signing_key_missing():
    """Print recovery instructions if the Claude signing key isn't on disk."""
    priv_key = CLAUDE_SIGNING_KEY.with_suffix("")
    pub_key = CLAUDE_SIGNING_KEY

    if is_dry_run() or priv_key.exists():
        return

    hostname = get_short_hostname()
    warn(f"Claude signing key missing: {priv_key}")
    info("Create it with one of the following:")
    info("")
    info("  # 1. Generate a fresh passphrase-less key:")
    info(
        f"  ssh-keygen -t ed25519 -N '' -C 'claude@{hostname}' "
        f"-f {priv_key}"
    )
    info("")
    info("  # 2. Back it up to 1Password as a document (adjust vault):")
    info(
        f"  op document create {priv_key} "
        f"--title='Claude Signing Key ({hostname})' --vault=Private"
    )
    info("")
    info("  # 3. Register the public key on GitHub as a signing key")
    info("  # (one-time: grant gh the admin:ssh_signing_key scope):")
    info("  gh auth refresh -h github.com -s admin:ssh_signing_key")
    info(f"  gh ssh-key add --type signing --title 'claude@{hostname}' {pub_key}")
    info("")
    info("Or, if the key already exists in 1Password, restore it with:")
    info(
        f"  op document get 'Claude Signing Key ({hostname})' --vault=Private "
        f"--out-file {priv_key}"
    )
    info(f"  chmod 600 {priv_key}")
    info(f"  ssh-keygen -y -f {priv_key} > {pub_key}")


def main():
    parse_dry_run()

    info("Installing Git...")

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

    migrate_legacy_files()
    generate_config()
    generate_allowed_signers()
    warn_if_claude_signing_key_missing()
    return 0


if __name__ == "__main__":
    sys.exit(main())
