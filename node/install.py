#!/usr/bin/env python3
"""Installation script for nvm and Node.js"""

import subprocess
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import info, success, error


def main():
    info("Installing nvm and Node.js...")

    xdg_data_home = os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))
    nvm_dir = Path(xdg_data_home) / 'nvm'

    if nvm_dir.exists() and (nvm_dir / 'nvm.sh').exists():
        success("nvm already installed")
    else:
        info("Installing nvm...")
        try:
            nvm_dir.mkdir(parents=True, exist_ok=True)

            env = os.environ.copy()
            env['NVM_DIR'] = str(nvm_dir)
            env['PROFILE'] = '/dev/null'

            nvm_url = (
                "https://raw.githubusercontent.com"
                "/nvm-sh/nvm/v0.40.1/install.sh"
            )
            subprocess.run(
                ['sh', '-c', f'curl -o- {nvm_url} | bash'],
                check=True,
                env=env
            )
            success("nvm installed")
        except subprocess.CalledProcessError:
            error("Failed to install nvm")
            return 1

    info("Installing Node.js LTS...")
    try:
        nvm_script = f'''
            export NVM_DIR="{nvm_dir}"
            [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
            nvm install --lts
            nvm use --lts
        '''
        subprocess.run(['bash', '-c', nvm_script], check=True)
        success("Node.js LTS installed")
        return 0
    except subprocess.CalledProcessError:
        error("Failed to install Node.js LTS")
        return 1


if __name__ == '__main__':
    sys.exit(main())
