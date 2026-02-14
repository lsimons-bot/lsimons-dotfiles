#!/usr/bin/env python3
"""Installation script for AWS CLI"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "script"))
from helpers import brew_install, brew_is_installed, error, info, success

AWS_CONFIG_DIR = Path.home() / ".aws"
AWS_CONFIG_FILE = AWS_CONFIG_DIR / "config"

DEFAULT_CONFIG = """\
[default]
region = eu-central-1
output = json
"""


def main():
    info("Installing AWS CLI...")

    if brew_is_installed("awscli"):
        success("awscli already installed")
    else:
        info("Installing awscli via Homebrew...")
        if not brew_install("awscli"):
            error("Failed to install awscli")
            return 1
        success("awscli installed")

    if AWS_CONFIG_FILE.exists():
        success(f"{AWS_CONFIG_FILE} already exists, skipping")
    else:
        info(f"Creating default {AWS_CONFIG_FILE}...")
        AWS_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        AWS_CONFIG_FILE.write_text(DEFAULT_CONFIG)
        success(f"Created {AWS_CONFIG_FILE}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
