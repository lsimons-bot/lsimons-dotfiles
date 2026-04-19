#!/usr/bin/env python3
"""Validation checks for lsimons-dotfiles.

Safe to run — does not modify anything. Used by CI and for local
verification before pushing.

Checks, in order:

  1. Python byte-compile for ``script/*.py`` and every ``*/install.py``
  2. Ruff linting for ``script/*.py``
  3. JSON validity for every tracked ``*.json`` file in the repo
  4. Installer dry-run: ``python3 script/install.py --dry-run``
     (exercises every topic installer with dry-run propagated)

Exits non-zero if any check fails.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_DIR = REPO_ROOT / 'script'


# Directories to skip when walking the repo for Python / JSON files.
SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv'}


def _walk_files(suffix: str) -> list[Path]:
    results: list[Path] = []
    for path in REPO_ROOT.rglob(f'*{suffix}'):
        if any(part in SKIP_DIRS for part in path.relative_to(REPO_ROOT).parts):
            continue
        results.append(path)
    return sorted(results)


def check_py_compile() -> bool:
    """Byte-compile every Python file under script/ and every */install.py."""
    targets: list[Path] = sorted(SCRIPT_DIR.glob('*.py'))
    targets += sorted(REPO_ROOT.glob('*/install.py'))

    print(f'[check] py_compile: {len(targets)} files')
    failed: list[str] = []
    for target in targets:
        try:
            subprocess.run(
                [sys.executable, '-m', 'py_compile', str(target)],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            failed.append(f'{target.relative_to(REPO_ROOT)}\n{exc.stderr}')

    if failed:
        print('[FAIL] py_compile errors:')
        for entry in failed:
            print(f'  - {entry}')
        return False
    print('[ok]   py_compile')
    return True


def check_ruff() -> bool:
    """Run ruff on script/*.py.

    Soft-fails (warns and skips) when ruff isn't on PATH, so first-run
    users without the full toolchain still get the other checks. Use
    `mise run check` (which installs ruff via .mise.toml's [tools]) or
    `pip install ruff` to get ruff coverage locally; CI installs it
    explicitly.
    """
    targets = sorted(SCRIPT_DIR.glob('*.py'))
    print(f'[check] ruff: {len(targets)} files')

    if shutil.which('ruff') is None:
        print('[WARN] ruff not on PATH; skipping. '
              'Install via `mise run check` or `pip install ruff`.')
        return True

    cmd = ['ruff', 'check', *[str(t) for t in targets], '--select=E,F,W']
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        print('[FAIL] ruff reported issues')
        return False
    print('[ok]   ruff')
    return True


def check_json() -> bool:
    """Validate every JSON file in the repo."""
    targets = _walk_files('.json')
    print(f'[check] json: {len(targets)} files')
    failed: list[str] = []
    for target in targets:
        try:
            with open(target, encoding='utf-8') as f:
                json.load(f)
        except json.JSONDecodeError as exc:
            failed.append(f'{target.relative_to(REPO_ROOT)}: {exc}')
        except OSError as exc:
            failed.append(f'{target.relative_to(REPO_ROOT)}: {exc}')

    if failed:
        print('[FAIL] JSON parse errors:')
        for entry in failed:
            print(f'  - {entry}')
        return False
    print('[ok]   json')
    return True


def check_install_dry_run() -> bool:
    """Run `script/install.py --dry-run` to exercise every topic installer."""
    install_py = SCRIPT_DIR / 'install.py'
    print('[check] install.py --dry-run')
    try:
        subprocess.run(
            [sys.executable, str(install_py), '--dry-run'],
            check=True,
            cwd=REPO_ROOT,
        )
    except subprocess.CalledProcessError:
        print('[FAIL] install.py --dry-run returned non-zero')
        return False
    print('[ok]   install.py --dry-run')
    return True


CHECKS = {
    'py_compile': check_py_compile,
    'ruff': check_ruff,
    'json': check_json,
    'install': check_install_dry_run,
}


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        '--only',
        choices=list(CHECKS),
        action='append',
        help='Run only the selected check(s). Repeatable.',
    )
    parser.add_argument(
        '--skip',
        choices=list(CHECKS),
        action='append',
        default=[],
        help='Skip the selected check(s). Repeatable.',
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    names = args.only if args.only else list(CHECKS)
    names = [n for n in names if n not in args.skip]

    print(f'[check] repo: {REPO_ROOT}')
    print(f'[check] running: {", ".join(names)}')
    print()

    failures: list[str] = []
    for name in names:
        if not CHECKS[name]():
            failures.append(name)
        print()

    if failures:
        print(f'[FAIL] checks failed: {", ".join(failures)}')
        return 1
    print('[ok]   all checks passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
