#!/usr/bin/env python3
"""Installation script for Tailscale.

Tailscale is the private network the remote-access topics rely on: the
`sshd/` and `wayvnc/` hosts bind or firewall to the tailnet, and every
other machine is a client. So it installs everywhere there is a package:

* macOS: the Tailscale app from Homebrew (the `tailscale-app` cask), which
  bundles the daemon and the menu-bar UI;
* Arch: the `tailscale` package, with `tailscaled` enabled as a system
  service;
* Debian/Ubuntu: nothing. Ubuntu's archive has no Tailscale and the
  vendor apt repository is not part of this repo's bootstrap, so the
  topic warns and moves on.

Joining the tailnet (`tailscale up`) opens a browser for the identity
provider and is the one interactive step; it is left to the user.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import (
    IS_ARCH,
    command_exists,
    ensure_package,
    info,
    is_dry_run,
    parse_dry_run,
    run_cmd,
    success,
    systemctl_enable,
    warn,
)

DAEMON_UNIT = "tailscaled"


def install_tailscale():
    return ensure_package(
        "Tailscale",
        brew="tailscale-app",
        cask=True,
        macos_app="Tailscale",
        pacman="tailscale",
        command="tailscale",
        optional=True,
    )


def report_login_state():
    """Say whether this machine has joined the tailnet; never log it in.

    `tailscale up` needs a browser and the user's identity provider, so
    the installer only points at it.
    """
    if is_dry_run() or not command_exists("tailscale"):
        return
    result = run_cmd(["tailscale", "status", "--peers=false"], check=False, capture_output=True)
    if result.returncode == 0:
        success("Tailscale is logged in")
        return
    warn("Tailscale is installed but not logged in; run `sudo tailscale up` to join the tailnet")


def main():
    parse_dry_run()
    info("Installing Tailscale...")

    if not install_tailscale():
        return 1

    if IS_ARCH and not systemctl_enable(DAEMON_UNIT):
        return 1

    report_login_state()
    return 0


if __name__ == '__main__':
    sys.exit(main())
