#!/usr/bin/env python3
"""Installation script for ZSH configuration"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "script"))
from helpers import install_symlinks, parse_dry_run


def main():
    parse_dry_run()
    install_symlinks(Path(__file__).resolve().parent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
