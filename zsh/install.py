#!/usr/bin/env python3
"""Installation script for ZSH configuration"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import info, success


def main():
    info("Setting up ZSH directories...")

    xdg_cache = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache'))
    xdg_state = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state'))

    zsh_cache = xdg_cache / 'zsh'
    zsh_state = xdg_state / 'zsh'

    zsh_cache.mkdir(parents=True, exist_ok=True)
    zsh_state.mkdir(parents=True, exist_ok=True)

    success("ZSH directories configured")
    return 0


if __name__ == '__main__':
    sys.exit(main())
