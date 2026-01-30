#!/usr/bin/env python3
"""Installation script for nvm and Node.js"""

import subprocess
import sys
import os
from pathlib import Path


def main():
    print("[INFO] Installing nvm and Node.js...")

    # Determine NVM_DIR
    xdg_data_home = os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))
    nvm_dir = Path(xdg_data_home) / 'nvm'

    # Check if nvm is already installed
    if nvm_dir.exists() and (nvm_dir / 'nvm.sh').exists():
        print("[SUCCESS] nvm already installed")
    else:
        print("[INFO] Installing nvm...")
        try:
            # Create NVM_DIR before install (nvm install script requires it to exist)
            nvm_dir.mkdir(parents=True, exist_ok=True)

            env = os.environ.copy()
            env['NVM_DIR'] = str(nvm_dir)

            # Install nvm
            subprocess.run(
                ['sh', '-c', 'curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash'],
                check=True,
                env=env
            )
            print("[SUCCESS] nvm installed")
        except subprocess.CalledProcessError:
            print("[ERROR] Failed to install nvm", file=sys.stderr)
            return 1

    # Install Node.js LTS using nvm
    print("[INFO] Installing Node.js LTS...")
    try:
        # Source nvm and install Node.js in a single shell
        nvm_script = f'''
            export NVM_DIR="{nvm_dir}"
            [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
            nvm install --lts
            nvm use --lts
        '''
        subprocess.run(['bash', '-c', nvm_script], check=True)
        print("[SUCCESS] Node.js LTS installed")
        return 0
    except subprocess.CalledProcessError:
        print("[ERROR] Failed to install Node.js LTS", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
