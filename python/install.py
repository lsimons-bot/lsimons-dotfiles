#!/usr/bin/env python3
"""Installation script for Python configuration"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import info, success, error, command_exists


def main():
    info("Checking Python installation...")

    if not command_exists('python3'):
        error("Python not found")
        return 1

    success("Python is installed")
    return 0


if __name__ == '__main__':
    sys.exit(main())
