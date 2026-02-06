#!/usr/bin/env python3
import sys
from pathlib import Path

# Add script directory to path for helpers
sys.path.append(str(Path(__file__).parent.parent / "script"))
from helpers import brew_install, brew_is_installed

def install():
    if brew_is_installed("ruby"):
        print("Ruby is already installed.")
        return
    print("Installing Ruby...")
    brew_install("ruby")

if __name__ == "__main__":
    install()
