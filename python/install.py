#!/usr/bin/env python3
"""Installation script for Python configuration"""

import subprocess
import sys


def main():
    print("[INFO] Checking Python installation...")

    # Verify Python is available (installed by main installer via Homebrew)
    result = subprocess.run(['which', 'python3'], capture_output=True)
    if result.returncode != 0:
        print("[ERROR] Python not found", file=sys.stderr)
        return 1

    print("[SUCCESS] Python is installed")
    return 0


if __name__ == '__main__':
    sys.exit(main())
