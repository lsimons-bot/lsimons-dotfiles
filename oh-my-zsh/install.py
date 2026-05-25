#!/usr/bin/env python3
"""Installation script for Oh My Zsh"""

import subprocess
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import (
    brew_install,
    brew_is_installed,
    error,
    info,
    is_dry_run,
    parse_dry_run,
    run_cmd,
    success,
)


def install_oh_my_zsh():
    info("Installing Oh My Zsh...")

    oh_my_zsh_dir = Path.home() / '.oh-my-zsh'
    if not is_dry_run() and oh_my_zsh_dir.exists():
        success("Oh My Zsh already installed")
        return True

    try:
        env = os.environ.copy()
        env['RUNZSH'] = 'no'
        env['CHSH'] = 'no'

        omz_url = (
            "https://raw.githubusercontent.com"
            "/ohmyzsh/ohmyzsh/master/tools/install.sh"
        )
        run_cmd(
            ['sh', '-c', f'curl -fsSL {omz_url} | sh'],
            check=True,
            env=env,
        )
        success("Oh My Zsh installed")
        return True
    except subprocess.CalledProcessError:
        error("Failed to install Oh My Zsh")
        return False


def install_powerlevel10k():
    info("Installing powerlevel10k...")

    if brew_is_installed('powerlevel10k'):
        success("powerlevel10k already installed")
        return True
    if brew_install('powerlevel10k'):
        success("powerlevel10k installed")
        return True
    error("Failed to install powerlevel10k")
    return False


def main():
    parse_dry_run()

    if not install_oh_my_zsh():
        return 1
    if not install_powerlevel10k():
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
