#!/usr/bin/env python3
"""Installation script for the Moonlight streaming client.

Moonlight is the client half of the Sunshine remote-desktop pair: it
connects to any machine whose `remoteAccess.sunshine` is enabled (see the
`sunshine/` topic) and streams its desktop with keyboard, mouse and audio.
It is installed on every desktop that has a package for it. Pairing
itself is interactive (a PIN shown by Moonlight, entered in Sunshine's web
UI once per client) and stays a manual step.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import ensure_package, info, parse_dry_run


def main():
    parse_dry_run()
    info("Installing Moonlight...")

    # Optional: Debian and Ubuntu do not package moonlight-qt (upstream
    # offers a Flatpak and an AppImage instead), so a missing client
    # there is a warning, not a failed install.
    if not ensure_package(
        'Moonlight',
        brew='moonlight',
        cask=True,
        macos_app='Moonlight',
        pacman='moonlight-qt',
        command='moonlight-qt',
        optional=True,
    ):
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
