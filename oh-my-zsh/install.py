#!/usr/bin/env python3
"""Installation script for Oh My Zsh"""

import subprocess
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import info, success, error


def main():
    info("Installing Oh My Zsh...")

    oh_my_zsh_dir = Path.home() / '.oh-my-zsh'
    if oh_my_zsh_dir.exists():
        success("Oh My Zsh already installed")
        return 0

    try:
        env = os.environ.copy()
        env['RUNZSH'] = 'no'
        env['CHSH'] = 'no'

        omz_url = (
            "https://raw.githubusercontent.com"
            "/ohmyzsh/ohmyzsh/master/tools/install.sh"
        )
        subprocess.run(
            ['sh', '-c', f'curl -fsSL {omz_url} | sh'],
            check=True,
            env=env
        )
        success("Oh My Zsh installed")
        return 0
    except subprocess.CalledProcessError:
        error("Failed to install Oh My Zsh")
        return 1


if __name__ == '__main__':
    sys.exit(main())
