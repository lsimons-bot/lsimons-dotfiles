#!/usr/bin/env python3
"""Installation script for SSH"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import info, success


def main():
    info("Configuring SSH...")

    ssh_dir = Path.home() / '.ssh'
    ssh_dir.mkdir(mode=0o700, exist_ok=True)

    # Ensure correct permissions
    current_mode = ssh_dir.stat().st_mode & 0o777
    if current_mode != 0o700:
        ssh_dir.chmod(0o700)
        info(f"Fixed ~/.ssh permissions: {oct(current_mode)} -> 0700")

    # Create empty config.local if it doesn't exist
    config_local = ssh_dir / 'config.local'
    if not config_local.exists():
        config_local.touch(mode=0o600)
        info("Created ~/.ssh/config.local")

    success("SSH configured")
    return 0


if __name__ == '__main__':
    sys.exit(main())
