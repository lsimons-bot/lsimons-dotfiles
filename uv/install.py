#!/usr/bin/env python3
"""Installation script for uv (Python package manager)"""

import subprocess
import sys


def main():
    print("[INFO] Installing uv...")

    # Check if already installed
    result = subprocess.run(['which', 'uv'], capture_output=True)
    if result.returncode == 0:
        print("[SUCCESS] uv already installed")
        return 0

    # Install via Homebrew
    try:
        subprocess.run(['brew', 'install', 'uv'], check=True)
        print("[SUCCESS] uv installed")
        return 0
    except subprocess.CalledProcessError:
        print("[ERROR] Failed to install uv", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
