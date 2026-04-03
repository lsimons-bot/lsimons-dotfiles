#!/usr/bin/env python3
"""Installation script for Claude Code"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import info, success, error, command_exists, brew_install


def link_directory(src, dst):
    """Create a symlink for a directory, backing up existing if needed."""
    src_path = Path(src)
    dst_path = Path(dst)

    if dst_path.is_symlink():
        if dst_path.resolve() == src_path.resolve():
            success(f"Already linked: {dst}")
            return True
        dst_path.unlink()
    elif dst_path.exists():
        # Backup existing directory
        backup = dst_path.with_suffix('.backup')
        info(f"Backing up {dst} to {backup}")
        if backup.exists():
            shutil.rmtree(backup)
        shutil.move(str(dst_path), str(backup))

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.symlink_to(src_path)
    success(f"Linked: {dst} -> {src}")
    return True


def get_git_email():
    """Get the global git user email."""
    result = subprocess.run(
        ['git', 'config', '--get', 'user.email'],
        capture_output=True, text=True
    )
    return result.stdout.strip() if result.returncode == 0 else None


def build_attribution(email):
    """Return the commit attribution string based on git email."""
    if email == 'bot@leosimons.com':
        return 'Co-Authored-By: Leo Simons <mail@leosimons.com>'
    else:
        return 'Co-Authored-By: lsimons-bot <bot@leosimons.com>'


def write_settings(claude_dir, topic_dir):
    """Write ~/.claude/settings.json from base config plus dynamic attribution."""
    base_file = topic_dir / 'settings.json.base'
    settings_path = claude_dir / 'settings.json'

    with open(base_file) as f:
        settings = json.load(f)

    email = get_git_email()
    if email:
        info(f"Detected git email: {email}")
        attribution_text = build_attribution(email)
        settings['attribution'] = {
            'commit': attribution_text,
            'pr': attribution_text,
        }
    else:
        info("No git email found; skipping attribution config")

    # If settings.json is currently a symlink, replace it with a real file
    if settings_path.is_symlink():
        settings_path.unlink()

    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=2)
        f.write('\n')

    success(f"Wrote: {settings_path}")


def main():
    info("Installing Claude Code...")

    if command_exists('claude'):
        success("Claude Code already installed")
    else:
        if brew_install('claude-code', cask=True):
            success("Claude Code installed")
        else:
            error("Failed to install Claude Code")
            return 1

    # Ensure ~/.claude directory exists
    claude_dir = Path.home() / '.claude'
    claude_dir.mkdir(parents=True, exist_ok=True)

    topic_dir = Path(__file__).resolve().parent

    # Link skills directory
    skills_src = topic_dir / 'skills'
    skills_dst = claude_dir / 'skills'
    if skills_src.exists():
        link_directory(skills_src, skills_dst)

    # Write settings.json with dynamic attribution
    write_settings(claude_dir, topic_dir)

    return 0


if __name__ == '__main__':
    sys.exit(main())
