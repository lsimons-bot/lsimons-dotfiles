#!/usr/bin/env python3
"""Installation script for tfenv and Terraform"""

import getpass
import grp
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import (
    IS_ARCH,
    XDG_DATA_HOME_STR,
    dry,
    ensure_package,
    error,
    info,
    is_dry_run,
    parse_dry_run,
    run_cmd,
    success,
    warn,
)

# The Arch `tfenv` package is not stock tfenv: it stores Terraform versions
# and the global version file in /var/lib/tfenv, writable by the `tfenv`
# group, and leaves TFENV_CONFIG_DIR at the root-owned /opt/tfenv. Stock
# tfenv, when it finds its config dir unwritable, asks interactively whether
# to fall back to ~/.tfenv. Point it at an XDG path instead so it never asks.
# On Arch the config dir only holds install locks and the optional
# use-gpgv/use-gnupg files; the versions still land in /var/lib/tfenv.
# terraform.sh exports the same path for interactive shells.
ARCH_TFENV_GROUP = 'tfenv'
ARCH_TFENV_CONFIG_DIR = os.path.join(XDG_DATA_HOME_STR, 'tfenv')


def ensure_tfenv_group_membership():
    """Add the current user to the Arch package's `tfenv` group.

    Returns True when the group is already active in this process, False
    when it is not (freshly added, or added in an earlier run without a
    re-login since). None means the group could not be joined.
    """
    user = getpass.getuser()

    if is_dry_run():
        dry(f"would add {user} to the {ARCH_TFENV_GROUP} group")
        return True

    try:
        group = grp.getgrnam(ARCH_TFENV_GROUP)
    except KeyError:
        error(f"No {ARCH_TFENV_GROUP} group exists; the tfenv package should create it")
        return None

    if group.gr_gid in os.getgroups():
        return True

    if user in group.gr_mem:
        warn(f"{user} is in the {ARCH_TFENV_GROUP} group but this session predates it")
        return False

    result = run_cmd(
        ['sudo', 'usermod', '-aG', ARCH_TFENV_GROUP, user], check=False, capture_output=True
    )
    if result.returncode != 0:
        error(
            f"Failed to add {user} to the {ARCH_TFENV_GROUP} group: "
            f"{(result.stderr or '').strip()}"
        )
        return None
    success(f"Added {user} to the {ARCH_TFENV_GROUP} group (log out and back in to pick it up)")
    return False


def tfenv_command(args, group_active):
    """Build a non-interactive tfenv invocation for this platform."""
    if not IS_ARCH:
        return ['tfenv', *args]
    cmd = ['env', f'TFENV_CONFIG_DIR={ARCH_TFENV_CONFIG_DIR}', 'tfenv', *args]
    if group_active:
        return cmd
    # The group only joins the process table at login. Until then, run
    # tfenv with it through sudo so this session can still write to
    # /var/lib/tfenv.
    return ['sudo', '-u', getpass.getuser(), '-g', ARCH_TFENV_GROUP, *cmd]


def main():
    parse_dry_run()
    info("Installing tfenv and Terraform...")

    if not ensure_package(
        'tfenv', brew='tfenv', aur='tfenv', mise='tfenv', command='tfenv'
    ):
        return 1

    group_active = True
    if IS_ARCH:
        group_active = ensure_tfenv_group_membership()
        if group_active is None:
            return 1
        if not is_dry_run():
            os.makedirs(ARCH_TFENV_CONFIG_DIR, exist_ok=True)

    info("Installing latest stable Terraform...")
    try:
        run_cmd(tfenv_command(['install', 'latest'], group_active), check=True)
        run_cmd(tfenv_command(['use', 'latest'], group_active), check=True)
        success("Terraform installed")
    except subprocess.CalledProcessError:
        error("Failed to install Terraform via tfenv")
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
