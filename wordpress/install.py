#!/usr/bin/env python3
"""Installation script for WordPress CLI"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import info, success, error, command_exists, brew_install


def install_wp_package(package: str) -> bool:
    """Install a wp-cli package if not already installed."""
    # Check if package is installed
    result = subprocess.run(
        ['wp', 'package', 'list', '--format=json'],
        capture_output=True,
        text=True
    )
    if result.returncode == 0 and package in result.stdout:
        return True

    # Install the package
    result = subprocess.run(['wp', 'package', 'install', package])
    return result.returncode == 0


def main():
    info("Installing WordPress CLI...")

    if not command_exists('wp'):
        if not brew_install('wp-cli'):
            error("Failed to install WordPress CLI")
            return 1
        success("WordPress CLI installed")
    else:
        success("WordPress CLI already installed")

    info("Installing wp-cli/restful package...")
    if install_wp_package('wp-cli/restful'):
        success("wp-cli/restful package installed")
    else:
        error("Failed to install wp-cli/restful package")
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
