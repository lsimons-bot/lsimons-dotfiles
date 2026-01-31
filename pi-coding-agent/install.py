#!/usr/bin/env python3
"""Installation script for pi-coding-agent"""

import subprocess
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import info, success, error, command_exists


def main():
    info("Installing pi-coding-agent...")

    if not command_exists('npm'):
        xdg_data_home = os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))
        nvm_dir = Path(xdg_data_home) / 'nvm'

        if not (nvm_dir / 'nvm.sh').exists():
            error("npm not found. Please install Node.js first (run node/install.py)")
            return 1

    # Check if already installed (via nvm environment)
    check_script = '''
        export NVM_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/nvm"
        [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
        which pi 2>/dev/null
    '''
    result = subprocess.run(['bash', '-c', check_script], capture_output=True)
    if result.returncode == 0:
        success("pi-coding-agent already installed")
        return 0

    try:
        install_script = '''
            export NVM_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/nvm"
            [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
            npm install -g @mariozechner/pi-coding-agent
        '''
        subprocess.run(['bash', '-c', install_script], check=True)
        success("pi-coding-agent installed")
        return 0
    except subprocess.CalledProcessError:
        error("Failed to install pi-coding-agent")
        return 1


if __name__ == '__main__':
    sys.exit(main())
