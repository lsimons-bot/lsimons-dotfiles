#!/usr/bin/env python3
"""Installation script for 1Password CLI"""

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import (
    DOTFILES_ROOT, info, success, error, command_exists,
    brew_install, get_machine_config,
)


def generate_env_file():
    """Generate combined env file from base .env.1password + machine secrets."""
    home = Path.home()
    xdg_config_home = Path(os.environ.get('XDG_CONFIG_HOME', home / '.config'))
    env_dir = xdg_config_home / '1password'
    env_file = env_dir / 'env'

    # Read base env file into ordered dict (var_name -> full line)
    base_env = DOTFILES_ROOT / '1password' / '.env.1password'
    entries = {}
    if base_env.exists():
        for line in base_env.read_text().splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                var_name = stripped.split('=', 1)[0]
                entries[var_name] = stripped

    # Merge machine-specific secrets (overrides base if same var name)
    machine_config, hostname = get_machine_config()
    op_config = machine_config.get('1password', {})
    secrets = op_config.get('secrets', {})
    for var_name, ref in sorted(secrets.items()):
        entries[var_name] = f'{var_name}="{ref}"'

    content = '\n'.join(entries.values()) + '\n'

    # Write env file
    env_dir.mkdir(parents=True, exist_ok=True)
    if env_file.exists() and env_file.read_text() == content:
        success("1Password env file already up to date")
    else:
        env_file.write_text(content)
        env_file.chmod(0o600)
        success(f"Generated 1Password env file for {hostname}")

    # Delete stale cache so next shell picks up new config
    xdg_cache_home = Path(os.environ.get('XDG_CACHE_HOME', home / '.cache'))
    cache_file = xdg_cache_home / '1password' / 'secrets.sh'
    if cache_file.exists():
        cache_file.unlink()
        info("Deleted stale secrets cache")

    return str(cache_file)


def install_launch_agent(cache_file_path):
    """Install LaunchAgent for cache cleanup on login/reboot."""
    home = Path.home()
    plist_name = 'com.lsimons.1password-cache-cleanup.plist'
    template = DOTFILES_ROOT / '1password' / plist_name
    agents_dir = home / 'Library' / 'LaunchAgents'
    dest = agents_dir / plist_name

    if not template.exists():
        error(f"LaunchAgent template not found: {template}")
        return False

    content = template.read_text().replace('__CACHE_FILE__', cache_file_path)

    agents_dir.mkdir(parents=True, exist_ok=True)

    # Unload old agent if present
    if dest.exists():
        subprocess.run(
            ['launchctl', 'unload', str(dest)],
            capture_output=True
        )

    # Check if content changed
    if dest.exists() and dest.read_text() == content:
        # Reload in case it was unloaded
        subprocess.run(
            ['launchctl', 'load', str(dest)],
            capture_output=True
        )
        success("LaunchAgent already up to date")
        return True

    dest.write_text(content)
    subprocess.run(['launchctl', 'load', str(dest)], capture_output=True)
    success("Installed 1Password cache cleanup LaunchAgent")
    return True


def main():
    info("Installing 1Password CLI...")

    if command_exists('op'):
        success("1Password CLI already installed")
    elif brew_install('1password-cli', cask=True):
        success("1Password CLI installed")
    else:
        error("Failed to install 1Password CLI")
        return 1

    cache_file_path = generate_env_file()
    install_launch_agent(cache_file_path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
