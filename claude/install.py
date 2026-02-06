#!/usr/bin/env python3
"""Installation script for Claude Code"""

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import info, success, error, command_exists, brew_install


def link_directory(src, dst):
    """Create a symlink for a directory, backing up existing if needed."""
    src_path = Path(src)
    dst_path = Path(dst)

    if dst_path.is_symlink():
        if dst_path.resolve() == src_path.resolve():
            success(f"Already linked: {dst}")
            return True
        dst_path.unlink()
    elif dst_path.exists():
        # Backup existing directory
        backup = dst_path.with_suffix('.backup')
        info(f"Backing up {dst} to {backup}")
        if backup.exists():
            shutil.rmtree(backup)
        shutil.move(str(dst_path), str(backup))

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.symlink_to(src_path)
    success(f"Linked: {dst} -> {src}")
    return True


def main():
    info("Installing Claude Code...")

    if command_exists('claude'):
        success("Claude Code already installed")
    else:
        if brew_install('claude-code', cask=True):
            success("Claude Code installed")
        else:
            error("Failed to install Claude Code")
            return 1

    # Ensure ~/.claude directory exists
    claude_dir = Path.home() / '.claude'
    claude_dir.mkdir(parents=True, exist_ok=True)

    # Link skills directory
    topic_dir = Path(__file__).resolve().parent
    skills_src = topic_dir / 'skills'
    skills_dst = claude_dir / 'skills'

    if skills_src.exists():
        link_directory(skills_src, skills_dst)

    return 0


if __name__ == '__main__':
    sys.exit(main())
