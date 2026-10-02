#!/usr/bin/env python3
"""Installation script for Oh My Zsh"""

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import (
    XDG_DATA_HOME_STR,
    command_exists,
    dry,
    ensure_package,
    error,
    info,
    install_symlinks,
    is_dry_run,
    parse_dry_run,
    run_cmd,
    success,
)

P10K_REPO = 'https://github.com/romkatv/powerlevel10k.git'
P10K_SOURCE_DIR = Path(XDG_DATA_HOME_STR) / 'powerlevel10k'


def install_oh_my_zsh():
    info("Installing Oh My Zsh...")

    oh_my_zsh_dir = Path.home() / '.oh-my-zsh'
    if not is_dry_run() and oh_my_zsh_dir.exists():
        success("Oh My Zsh already installed")
        return True

    try:
        env = os.environ.copy()
        env['RUNZSH'] = 'no'
        env['CHSH'] = 'no'

        omz_url = (
            "https://raw.githubusercontent.com"
            "/ohmyzsh/ohmyzsh/master/tools/install.sh"
        )
        run_cmd(
            ['sh', '-c', f'curl -fsSL {omz_url} | sh'],
            check=True,
            env=env,
        )
        success("Oh My Zsh installed")
        return True
    except subprocess.CalledProcessError:
        error("Failed to install Oh My Zsh")
        return False


def powerlevel10k_theme_paths():
    """Every place a packaged or cloned theme can be, as oh-my-zsh/rc.zsh
    searches them."""
    candidates = []
    if command_exists('brew'):
        prefix = run_cmd(
            ['brew', '--prefix', 'powerlevel10k'], check=False, capture_output=True
        )
        if prefix.returncode == 0:
            candidates.append(
                Path(prefix.stdout.strip()) / 'share/powerlevel10k/powerlevel10k.zsh-theme'
            )
    candidates += [
        Path('/usr/share/zsh-theme-powerlevel10k/powerlevel10k.zsh-theme'),
        Path('/usr/local/share/powerlevel10k/powerlevel10k.zsh-theme'),
        P10K_SOURCE_DIR / 'powerlevel10k.zsh-theme',
    ]
    return candidates


def install_powerlevel10k():
    info("Installing powerlevel10k...")

    # Homebrew and the AUR package the theme (Arch names the package after
    # what it is rather than after the theme); Debian/Ubuntu do not, so
    # there it is cloned from upstream instead, which is also romkatv's
    # own recommended install. oh-my-zsh/rc.zsh knows every one
    # of these locations.
    if not ensure_package(
        'powerlevel10k',
        brew='powerlevel10k',
        aur='zsh-theme-powerlevel10k',
        optional=True,
    ):
        return False

    if is_dry_run():
        dry(f"would clone {P10K_REPO} into {P10K_SOURCE_DIR} if no packaged theme is found")
        return True
    if any(path.is_file() for path in powerlevel10k_theme_paths()):
        success("powerlevel10k theme present")
        return True

    info(f"No packaged powerlevel10k theme; cloning into {P10K_SOURCE_DIR}...")
    try:
        run_cmd(['git', 'clone', '--depth=1', P10K_REPO, str(P10K_SOURCE_DIR)], check=True)
    except subprocess.CalledProcessError:
        error("Failed to clone powerlevel10k")
        return False
    success("powerlevel10k cloned")
    return True


def main():
    parse_dry_run()

    install_symlinks(Path(__file__).resolve().parent)
    if not install_oh_my_zsh():
        return 1
    if not install_powerlevel10k():
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
