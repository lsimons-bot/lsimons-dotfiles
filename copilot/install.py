#!/usr/bin/env python3
"""Installation script for GitHub Copilot CLI"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "script"))
from helpers import brew_install, brew_is_installed, error, info, success


def install_copilot_cli():
    """Install copilot-cli via Homebrew"""
    info("Installing copilot-cli...")

    if brew_is_installed("copilot-cli"):
        success("copilot-cli already installed")
        return 0

    if brew_install("copilot-cli"):
        success("copilot-cli installed")
        return 0

    error("Failed to install copilot-cli")
    return 1


def configure_copilot():
    """Configure copilot-instructions.md symlink"""
    home = Path.home()
    dotfiles = home / ".dotfiles"
    copilot_dir = home / ".copilot"
    instructions_md = copilot_dir / "copilot-instructions.md"
    claude_md_source = dotfiles / "claude" / "CLAUDE.md.symlink"

    # Ensure ~/.copilot exists
    copilot_dir.mkdir(parents=True, exist_ok=True)

    # Symlink copilot-instructions.md -> claude/CLAUDE.md.symlink
    if instructions_md.is_symlink():
        current = instructions_md.resolve()
        if current == claude_md_source.resolve():
            success("copilot-instructions.md already linked correctly")
        else:
            info(f"copilot-instructions.md points to {current}, relinking")
            instructions_md.unlink()
            instructions_md.symlink_to(claude_md_source)
            success(f"Linked copilot-instructions.md -> {claude_md_source}")
    elif instructions_md.exists():
        info("copilot-instructions.md exists as regular file, replacing with symlink")
        instructions_md.unlink()
        instructions_md.symlink_to(claude_md_source)
        success(f"Linked copilot-instructions.md -> {claude_md_source}")
    else:
        instructions_md.symlink_to(claude_md_source)
        success(f"Linked copilot-instructions.md -> {claude_md_source}")


def main():
    info("Setting up GitHub Copilot CLI...")

    result = install_copilot_cli()
    if result != 0:
        return result

    configure_copilot()
    return 0


if __name__ == "__main__":
    sys.exit(main())
