#!/usr/bin/env python3
"""Installation script for tmux"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import brew_install, command_exists, error, info, install_symlinks, success


def main():
    install_symlinks(Path(__file__).resolve().parent)

    info("Installing tmux...")

    if command_exists('tmux'):
        success("tmux already installed")
        return 0

    if brew_install('tmux'):
        success("tmux installed")
        return 0

    error("Failed to install tmux")
    return 1


if __name__ == '__main__':
    sys.exit(main())
