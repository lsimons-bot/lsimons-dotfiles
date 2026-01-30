#!/usr/bin/env python3
"""Installation script for Oh My Zsh"""

import subprocess
import sys
import os
from pathlib import Path


def main():
    print("[INFO] Installing Oh My Zsh...")

    # Check if already installed
    oh_my_zsh_dir = Path.home() / '.oh-my-zsh'
    if oh_my_zsh_dir.exists():
        print("[SUCCESS] Oh My Zsh already installed")
        return 0

    # Install Oh My Zsh (unattended mode)
    try:
        env = os.environ.copy()
        env['RUNZSH'] = 'no'  # Don't run zsh after install
        env['CHSH'] = 'no'    # Don't change shell

        subprocess.run(
            ['sh', '-c', 'curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh | sh'],
            check=True,
            env=env
        )
        print("[SUCCESS] Oh My Zsh installed")
        return 0
    except subprocess.CalledProcessError:
        print("[ERROR] Failed to install Oh My Zsh", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
