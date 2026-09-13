#!/usr/bin/env python3
"""Installation script for the Sunshine remote-desktop host.

Opt-in per machine through `remoteAccess.sunshine` in
`machines/<hostname>.json`; every other machine skips this topic. On an
enabled machine it:

* installs Sunshine from the prebuilt `sunshine-bin` package rather than
  the source `sunshine` package, which clones a dozen submodules and
  compiles for the better part of an hour;
* installs the VA-API driver named in `remoteAccess.vaapiDriver`, if
  any, so encoding happens on the GPU (`libva-intel-driver` for Intel
  before Broadwell, `intel-media-driver` after; Mesa covers AMD);
* reloads udev so Sunshine's rule granting the desktop user `/dev/uinput`
  (keyboard and mouse injection) applies without a reboot;
* enables Sunshine's systemd user unit;
* opens Sunshine's ports in ufw, restricted to `remoteAccess.allowFrom`
  when that is set.

Sunshine's own configuration (admin credentials, paired clients) lives in
`~/.config/sunshine/` and is created interactively through its web UI at
https://localhost:47990 — only from localhost, as any other origin trips
its CSRF check.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import (
    IS_ARCH,
    dry,
    ensure_package,
    error,
    get_remote_access_config,
    info,
    is_dry_run,
    pacman_is_installed,
    parse_dry_run,
    run_cmd,
    success,
    systemctl_enable,
    ufw_allow,
    warn,
)

PACKAGE = "sunshine-bin"
UNIT = "app-dev.lizardbyte.app.Sunshine.service"

# Sunshine's fixed port map (base 47989): HTTPS/HTTP for pairing and the
# session handshake, RTSP for stream setup, then the video, control and
# audio UDP streams. The web UI (47990) is deliberately left closed.
TCP_PORTS = "47984,47989,48010"
UDP_PORTS = "47998:48000"


def install_sunshine():
    fresh = not pacman_is_installed(PACKAGE)
    if not ensure_package("Sunshine", aur=PACKAGE, command="sunshine"):
        return False
    if fresh:
        reload_udev()
    return True


def reload_udev():
    """Apply 60-sunshine.rules (uinput access) now rather than on reboot."""
    if is_dry_run():
        dry("would run: sudo udevadm control --reload-rules && sudo udevadm trigger")
        return
    for cmd in (
        ["sudo", "udevadm", "control", "--reload-rules"],
        ["sudo", "udevadm", "trigger"],
    ):
        result = run_cmd(cmd, check=False, capture_output=True)
        if result.returncode != 0:
            warn(f"{' '.join(cmd)} failed: {(result.stderr or '').strip()}")
            warn("Keyboard and mouse input may not work until the next reboot")
            return
    success("udev rules reloaded")


def install_vaapi_driver(driver):
    return ensure_package(f"VA-API driver ({driver})", pacman=driver)


def open_firewall(allow_from):
    ok = ufw_allow(TCP_PORTS, "tcp", "sunshine", from_cidr=allow_from)
    return ufw_allow(UDP_PORTS, "udp", "sunshine", from_cidr=allow_from) and ok


def main():
    parse_dry_run()

    remote = get_remote_access_config()
    if not remote.get("sunshine"):
        info("remoteAccess.sunshine is not enabled for this machine; skipping Sunshine")
        return 0

    if not IS_ARCH:
        error("Sunshine hosting is only set up for Arch here (sunshine-bin from the AUR)")
        return 1

    info("Installing the Sunshine remote-desktop host...")
    if not install_sunshine():
        return 1

    driver = remote.get("vaapiDriver")
    if driver and not install_vaapi_driver(driver):
        return 1

    if not systemctl_enable(UNIT, user=True):
        return 1

    if not open_firewall(remote.get("allowFrom")):
        return 1

    info("Pair clients from https://localhost:47990 (localhost only: other origins fail CSRF)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
