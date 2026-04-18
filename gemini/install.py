#!/usr/bin/env python3
"""Installation script for Gemini CLI"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import info, success, error, command_exists, brew_install


def configure_gemini():
    home = Path.home()
    dotfiles = home / '.dotfiles'
    gemini_dir = home / '.gemini'
    gemini_md = gemini_dir / 'GEMINI.md'
    claude_md_source = dotfiles / 'claude' / 'CLAUDE.md.symlink'

    gemini_dir.mkdir(parents=True, exist_ok=True)

    if gemini_md.is_symlink():
        if gemini_md.resolve() == claude_md_source.resolve():
            success("GEMINI.md already linked correctly")
            return
        gemini_md.unlink()
    elif gemini_md.exists():
        gemini_md.unlink()

    gemini_md.symlink_to(claude_md_source)
    success(f"Linked GEMINI.md -> {claude_md_source}")


def main():
    info("Installing Gemini CLI...")

    if command_exists('gemini'):
        success("Gemini CLI already installed")
    elif brew_install('gemini-cli'):
        success("Gemini CLI installed")
    else:
        error("Failed to install Gemini CLI")
        return 1

    configure_gemini()
    return 0


if __name__ == '__main__':
    sys.exit(main())
