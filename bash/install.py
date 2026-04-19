#!/usr/bin/env python3
"""Installation script for Bash configuration"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import info, install_symlinks, success


def main():
    install_symlinks(Path(__file__).resolve().parent)

    info("Setting up Bash directories...")

    xdg_state = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state'))

    bash_state = xdg_state / 'bash'
    bash_state.mkdir(parents=True, exist_ok=True)

    success("Bash directories configured")
    return 0


if __name__ == '__main__':
    sys.exit(main())
