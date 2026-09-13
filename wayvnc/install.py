#!/usr/bin/env python3
"""Installation script for the wayvnc remote-desktop host.

Opt-in per machine through `remoteAccess.wayvnc` in
`machines/<hostname>.json`; every other machine skips this topic. On an
enabled machine it:

* installs wayvnc, a VNC server for wlroots-style Wayland compositors
  (Hyprland implements the screencopy and virtual-input protocols it
  needs);
* writes and enables a systemd user unit that starts wayvnc with the
  desktop session, bound to this machine's Tailscale IPv4 address and
  nothing else. The address is looked up at start time, so the unit
  survives the node being re-enrolled;
* opens 5900/tcp in ufw for the tailnet's CGNAT range only.

wayvnc is chosen over Sunshine deliberately: it copies frames through
shared memory and encodes on the CPU, so it never touches the GPU buffer
path that exhausted memory on snow. Access control is the tailnet; VNC
auth is not enabled, which is why the bind address matters.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import (
    IS_ARCH,
    XDG_CONFIG_HOME,
    dry,
    ensure_package,
    error,
    get_remote_access_config,
    info,
    is_dry_run,
    parse_dry_run,
    run_cmd,
    success,
    systemctl_enable,
    ufw_allow,
    write_file,
)

PORT = 5900
# Tailscale hands every node an address from this range.
TAILNET_CIDR = "100.64.0.0/10"

UNIT_NAME = "wayvnc.service"
UNIT_PATH = XDG_CONFIG_HOME / "systemd" / "user" / UNIT_NAME
UNIT = f"""\
# Managed by lsimons-dotfiles (wayvnc/install.py). Do not edit by hand.
[Unit]
Description=wayvnc remote desktop, bound to this machine's Tailscale address
After=graphical-session.target
PartOf=graphical-session.target

[Service]
# The tailnet address is looked up on every start; tailscaled may not be
# up yet when the session starts, which Restart= covers.
ExecStart=/bin/sh -c 'exec wayvnc "$(tailscale ip -4)" {PORT}'
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=graphical-session.target
"""


def install_wayvnc():
    return ensure_package("wayvnc", pacman="wayvnc", command="wayvnc")


def install_unit():
    """Write the user unit and make systemd see it. Returns True on success."""
    if UNIT_PATH.exists() and UNIT_PATH.read_text() == UNIT:
        success(f"{UNIT_PATH} already up to date")
        return True
    write_file(UNIT_PATH, UNIT)
    if is_dry_run():
        dry("would run: systemctl --user daemon-reload")
        return True
    result = run_cmd(["systemctl", "--user", "daemon-reload"], check=False, capture_output=True)
    if result.returncode != 0:
        error(f"systemctl --user daemon-reload failed: {(result.stderr or '').strip()}")
        return False
    success(f"Wrote {UNIT_PATH}")
    return True


def main():
    parse_dry_run()

    remote = get_remote_access_config()
    if not remote.get("wayvnc"):
        info("remoteAccess.wayvnc is not enabled for this machine; skipping wayvnc")
        return 0

    if not IS_ARCH:
        error("wayvnc hosting is only set up for Arch here")
        return 1

    info("Installing the wayvnc remote-desktop host...")
    if not install_wayvnc():
        return 1
    if not install_unit():
        return 1
    if not systemctl_enable(UNIT_NAME, user=True):
        return 1
    if not ufw_allow(PORT, "tcp", "wayvnc", from_cidr=TAILNET_CIDR):
        return 1

    info(f"Connect a VNC viewer to this machine's tailnet name on port {PORT}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
