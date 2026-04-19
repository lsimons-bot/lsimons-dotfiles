"""Common helper functions for topic install scripts."""

import json
import os
import shutil
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Root of the dotfiles repository
DOTFILES_ROOT = Path(__file__).resolve().parent.parent


def info(msg):
    """Print an info message."""
    print(f"[INFO] {msg}")


def success(msg):
    """Print a success message."""
    print(f"[SUCCESS] {msg}")


def warn(msg):
    """Print a warning message."""
    print(f"[WARN] {msg}")


def error(msg):
    """Print an error message to stderr."""
    print(f"[ERROR] {msg}", file=sys.stderr)


def command_exists(cmd):
    """Check if a command exists in PATH."""
    result = subprocess.run(['which', cmd], capture_output=True)
    return result.returncode == 0


def app_exists(app_name):
    """Check if a macOS app exists in /Applications.

    Args:
        app_name: Name without .app suffix (e.g., 'Brave Browser')
    """
    return Path(f'/Applications/{app_name}.app').exists()


def brew_install(package, cask=False):
    """Install a package via Homebrew.

    Args:
        package: The brew formula or cask name
        cask: If True, install as cask (--cask flag)

    Returns:
        True on success, False on failure
    """
    cmd = ['brew', 'install']
    if cask:
        cmd.append('--cask')
    cmd.append(package)

    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def brew_is_installed(package):
    """Check if a package is installed via Homebrew."""
    result = subprocess.run(['brew', 'list', package], capture_output=True)
    return result.returncode == 0


def get_short_hostname():
    """Get short hostname (without domain suffix)."""
    return socket.gethostname().split('.')[0]


def _deep_merge(base, override):
    """Recursively merge override into base, returning a new dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def backup_file(file_path):
    """Back up an existing file or symlink before it's replaced."""
    path = Path(file_path)
    if path.exists() or path.is_symlink():
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = Path.home() / '.dotfiles-backup' / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)
        dest = backup_dir / path.name
        shutil.move(str(path), str(dest))
        info(f"Backed up {file_path} to {dest}")


def link_file(src, dst):
    """Symlink src to dst, backing up anything already at dst."""
    src_path = Path(src)
    dst_path = Path(dst)

    if dst_path.is_symlink():
        current_src = dst_path.resolve()
        if current_src == src_path.resolve():
            success(f"Already linked: {dst}")
            return True
        warn(f"Symlink exists but points elsewhere: {dst} -> {current_src}")
        backup_file(dst)
    elif dst_path.exists():
        warn(f"File exists: {dst}")
        backup_file(dst)

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.symlink_to(src_path)
    success(f"Linked: {dst} -> {src}")
    return True


def load_symlink_mappings(topic_dir):
    """Load symlink destination overrides from <topic>/symlinks.txt.

    Each non-comment line has the form ``source.symlink -> destination``.
    ``$HOME``, ``$XDG_CONFIG_HOME``, and ``~`` are expanded in destinations.
    """
    topic_dir = Path(topic_dir)
    mappings = {}
    symlinks_file = topic_dir / 'symlinks.txt'
    if not symlinks_file.exists():
        return mappings

    home = Path.home()
    xdg_config_home = Path(
        os.environ.get('XDG_CONFIG_HOME', home / '.config')
    )

    for line in symlinks_file.read_text().strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if ' -> ' not in line:
            continue

        src_name, dst_path = line.split(' -> ', 1)
        src_name = src_name.strip()
        dst_path = dst_path.strip()

        dst_path = dst_path.replace('$HOME', str(home))
        dst_path = dst_path.replace('$XDG_CONFIG_HOME', str(xdg_config_home))
        dst_path = dst_path.replace('~', str(home))

        mappings[src_name] = Path(dst_path)

    return mappings


def install_symlinks(topic_dir):
    """Install every ``*.symlink`` file in ``topic_dir``.

    Destinations come from ``symlinks.txt`` when present; otherwise each
    file is linked to ``~/.<basename>`` (the filename without ``.symlink``).
    """
    topic_dir = Path(topic_dir)
    symlink_files = sorted(topic_dir.glob('*.symlink'))
    if not symlink_files:
        return True

    mappings = load_symlink_mappings(topic_dir)
    home = Path.home()

    all_ok = True
    for src in symlink_files:
        if not src.is_file():
            continue
        dst = mappings.get(src.name, home / f'.{src.stem}')
        if not link_file(src, dst):
            all_ok = False

    return all_ok


def get_machine_config():
    """Load machine-specific configuration.

    Always loads machines/default.json, then merges machines/<hostname>.json
    on top if it exists.

    Returns:
        tuple: (config_dict, hostname)
    """
    hostname = get_short_hostname()
    machines_dir = DOTFILES_ROOT / 'machines'

    # Always load default first
    with open(machines_dir / 'default.json') as f:
        config = json.load(f)

    # Merge hostname-specific config if it exists
    host_config_file = machines_dir / f'{hostname}.json'
    if host_config_file.exists():
        with open(host_config_file) as f:
            config = _deep_merge(config, json.load(f))

    return config, hostname
