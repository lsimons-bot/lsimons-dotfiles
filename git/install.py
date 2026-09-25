#!/usr/bin/env python3
"""Installation script for Git"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "script"))
from helpers import (
    AI_KEY_PUB_PATH,
    IS_MACOS,
    IS_WSL,
    SSH_CONFIG_AI_PATH,
    SSH_SIGN_BRIDGE_PATH,
    backup_file,
    command_exists,
    ensure_package,
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

# 1Password's SSH signing shim, shipped inside the desktop app. The macOS
# path is inside the .app bundle; the Linux package installs it under
# /opt alongside the rest of the app. Under WSL the app runs on Windows,
# so ssh/install.py generates a helper that signs with ssh-keygen through
# the bridged agent instead.
if IS_MACOS:
    GPG_SSH_PROGRAM_DEFAULT = "/Applications/1Password.app/Contents/MacOS/op-ssh-sign"
elif IS_WSL:
    GPG_SSH_PROGRAM_DEFAULT = str(SSH_SIGN_BRIDGE_PATH)
else:
    GPG_SSH_PROGRAM_DEFAULT = "/opt/1Password/op-ssh-sign"

# Editors to try for `core.editor`, most preferred first. Zed is the
# daily driver, but it has no aarch64 Linux build, so fall back rather
# than configure git to launch a binary that is not there. Each entry is
# (command, git core.editor value).
EDITOR_CANDIDATES = [
    ("zed", "zed --wait"),
    ("zeditor", "zeditor --wait"),
    ("nvim", "nvim"),
    ("vim", "vim"),
]
EDITOR_FALLBACK = "vim"

# Credential helpers. Git Credential Manager is preferred and main()
# installs it where a package exists (Homebrew cask, AUR). Debian and
# Ubuntu, WSL included, have no GCM package, so there the GitHub CLI
# stands in: `gh auth git-credential` answers for github.com (and any
# other host `gh auth login` was run for) with gh's own token and stays
# silent for everything else, which then falls through to git's prompt.
# gh is not probed for: the `gh` topic depends on this one and so runs
# later, and git only invokes the helper at fetch/push time anyway.
CREDENTIAL_HELPER_GCM = "manager"
CREDENTIAL_HELPER_GH = "!gh auth git-credential"


def resolve_editor():
    """Return the `core.editor` value for the first editor present."""
    for command, editor in EDITOR_CANDIDATES:
        if command_exists(command):
            return editor
    warn(
        "None of "
        + ", ".join(command for command, _ in EDITOR_CANDIDATES)
        + f" found; falling back to {EDITOR_FALLBACK} for core.editor"
    )
    return EDITOR_FALLBACK


def resolve_credential_helper():
    """Return the `credential.helper` value: GCM if installed, else gh."""
    if command_exists("git-credential-manager"):
        return CREDENTIAL_HELPER_GCM
    info(
        "git-credential-manager not found; using "
        f"'{CREDENTIAL_HELPER_GH}' as credential.helper"
    )
    return CREDENTIAL_HELPER_GH


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
    # Signing is on unless a machine turns it off explicitly with
    # `git.sign: false` (the lab machines, which hold no SSH keys).
    gpgsign = "true" if machine_config["git"].get("sign", True) else "false"
    if gpgsign == "false":
        info(f"Commit signing is disabled for {hostname}")
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
    credential_helper = resolve_credential_helper()

    main_content = _render_config(
        template,
        allowed_signers_file=str(_xdg_git_dir() / "allowed-signers"),
        name=git_user["name"],
        email=git_user["email"],
        gpgsign=gpgsign,
        signingkey=signing_key_pub,
        gpg_ssh_program=GPG_SSH_PROGRAM_DEFAULT,
        editor=resolve_editor(),
        credential_helper=credential_helper,
        ssh_command_block="",
    )
    ai_content = _render_config(
        template,
        allowed_signers_file=str(_xdg_git_dir() / "allowed-signers"),
        name=git_user["name"],
        email=git_user["email"],
        gpgsign=gpgsign,
        signingkey=str(AI_KEY_PUB_PATH),
        gpg_ssh_program="ssh-keygen",
        editor="vim",
        credential_helper=credential_helper,
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

    # Fail fast, before touching any files, if this machine isn't enrolled
    # (get_machine_config() exits with an error in that case). The result
    # is cached, so generate_config()/generate_allowed_signers() below reuse
    # it for free.
    get_machine_config()

    migrate_legacy_files()

    if not ensure_package("Git", brew="git", pacman="git", apt="git"):
        return 1

    # Optional on Linux: git-credential-manager publishes a .deb/.rpm and
    # an AUR build that pulls in the whole .NET runtime, and Debian/Ubuntu
    # have no package at all. generate_config() below picks GCM when it
    # is present and `gh auth git-credential` otherwise, which is why the
    # config is written after this step rather than before.
    if not ensure_package(
        "Git Credential Manager",
        brew="git-credential-manager",
        cask=True,
        aur="git-credential-manager",
        command="git-credential-manager",
        optional=True,
    ):
        return 1

    generate_config()
    generate_allowed_signers()

    if not ensure_package(
        "git-filter-repo",
        brew="git-filter-repo",
        pacman="git-filter-repo",
        apt="git-filter-repo",
        command="git-filter-repo",
    ):
        return 1

    lfs_already_installed = command_exists("git-lfs")
    if not ensure_package("git-lfs", brew="git-lfs", pacman="git-lfs", apt="git-lfs"):
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
