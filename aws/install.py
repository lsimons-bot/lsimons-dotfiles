#!/usr/bin/env python3
"""Installation script for AWS CLI + saml2aws"""

import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "script"))
from helpers import (
    command_exists,
    ensure_package,
    error,
    info,
    is_dry_run,
    parse_dry_run,
    run_cmd,
    success,
    write_file,
)

AWS_CONFIG_DIR = Path.home() / ".aws"
AWS_CONFIG_FILE = AWS_CONFIG_DIR / "config"
SAML2AWS_CONFIG_FILE = Path.home() / ".saml2aws"

DEFAULT_CONFIG = """\
[default]
region = eu-central-1
output = json
"""

# Our Okta org runs OIE, which disables the classic /api/v1/authn API that
# saml2aws's default Okta provider depends on, so that provider always fails
# with 401 even with correct credentials. The Browser provider drives an
# actual browser through the login flow instead, so it works with OIE.
SAML2AWS_SETTINGS = {
    "provider": "Browser",
    "download_browser_driver": "true",
}


def set_ini_value(path, section, key, value):
    """Idempotently set ``key = value`` under ``[section]`` in an ini-style file.

    saml2aws itself writes plain, often-unquoted values (URLs, usernames)
    into this file, which isn't valid TOML, so this can't reuse
    helpers.set_toml_value (which parses with tomllib). Only the one key is
    managed: all other content, comments, and formatting are preserved.
    """
    setting_line = f"{key} = {value}"
    text = path.read_text() if path.exists() else ""

    if not text:
        write_file(path, f"[{section}]\n{setting_line}\n")
        success(f"Created {path} with {setting_line}")
        return

    lines = text.splitlines(keepends=True)
    header_re = re.compile(rf"^\s*\[{re.escape(section)}\]\s*$")
    boundary_re = re.compile(r"^\s*\[")
    key_re = re.compile(rf"^\s*{re.escape(key)}\s*=")

    section_start = next((i for i, line in enumerate(lines) if header_re.match(line)), None)
    if section_start is None:
        sep = "\n" if text.endswith("\n") else "\n\n"
        write_file(path, f"{text}{sep}[{section}]\n{setting_line}\n")
        success(f"Added [{section}] {setting_line} to {path}")
        return

    section_end = next(
        (j for j in range(section_start + 1, len(lines)) if boundary_re.match(lines[j])),
        len(lines),
    )
    for j in range(section_start + 1, section_end):
        if key_re.match(lines[j]):
            if lines[j].strip() == setting_line:
                success(f"{path}: [{section}] {key} already set")
                return
            nl = "\n" if lines[j].endswith("\n") else ""
            lines[j] = setting_line + nl
            write_file(path, "".join(lines))
            success(f"Set {setting_line} in {path}")
            return

    lines.insert(section_start + 1, setting_line + "\n")
    write_file(path, "".join(lines))
    success(f"Set {setting_line} in {path}")


def main():
    parse_dry_run()
    info("Installing AWS CLI...")

    if not ensure_package(
        "awscli", brew="awscli", pacman="aws-cli-v2", mise="aws-cli", command="aws"
    ):
        return 1

    if AWS_CONFIG_FILE.exists():
        success(f"{AWS_CONFIG_FILE} already exists, skipping")
    else:
        info(f"Creating default {AWS_CONFIG_FILE}...")
        write_file(AWS_CONFIG_FILE, DEFAULT_CONFIG)
        success(f"Created {AWS_CONFIG_FILE}")

    info("Installing saml2aws...")
    if not ensure_package(
        "saml2aws", brew="saml2aws", aur="saml2aws", mise="saml2aws", command="saml2aws"
    ):
        return 1

    for key, value in SAML2AWS_SETTINGS.items():
        set_ini_value(SAML2AWS_CONFIG_FILE, "default", key, value)

    info("Installing Playwright's Chromium driver for saml2aws's Browser provider...")
    if not command_exists("pnpm") and not is_dry_run():
        error("pnpm not found; install the 'node' topic first")
        return 1
    # pnpm is a corepack shim (see the node topic). The first invocation
    # after `corepack enable pnpm` downloads the pnpm binary, and corepack
    # asks "Do you want to continue? [Y/n]" before doing so. Installers
    # must be non-interactive, so opt out of that prompt.
    env = {**os.environ, "COREPACK_ENABLE_DOWNLOAD_PROMPT": "0"}
    try:
        run_cmd(["pnpm", "dlx", "playwright", "install", "chromium"], env=env)
        success("Playwright Chromium driver installed")
    except subprocess.CalledProcessError:
        error("Failed to install Playwright's Chromium driver")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
