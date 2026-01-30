#!/usr/bin/env python3
"""Installation script for ZSH configuration"""

import sys
from pathlib import Path
import os


def main():
    print("[INFO] Setting up ZSH directories...")

    # Get XDG paths
    xdg_cache = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache'))
    xdg_state = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state'))

    # Ensure ZSH directories exist
    zsh_cache = xdg_cache / 'zsh'
    zsh_state = xdg_state / 'zsh'

    zsh_cache.mkdir(parents=True, exist_ok=True)
    zsh_state.mkdir(parents=True, exist_ok=True)

    print("[SUCCESS] ZSH directories configured")
    return 0


if __name__ == '__main__':
    sys.exit(main())
