#!/usr/bin/env python3
"""Validation checks for lsimons-dotfiles.

Safe to run — does not modify anything. Used by CI and for local
verification before pushing.

Checks, in order:

  1. Compile every Python file in memory (without creating ``__pycache__``)
  2. Ruff linting for every Python file
  3. ShellCheck over every ``.sh`` and ``.bash`` file
  4. actionlint over the GitHub Actions workflows
  5. JSON validity and machine configuration validation
  6. Standard-library unit tests
  7. Installer dry-run: ``python3 script/install.py --dry-run``
     (exercises every topic installer with dry-run propagated)

Every external tool used here is exact-pinned in ``.mise.toml``, so
``mise run check`` provisions all of them. Running this script bare,
without those tools on PATH, fails loudly rather than skipping silently.

Exits non-zero if any check fails.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_DIR = REPO_ROOT / 'script'


# Directories to skip when walking the repo for Python / JSON files.
SKIP_DIRS = {'.git', '.system', 'node_modules', '__pycache__', '.venv', 'venv'}


def _walk_files(suffix: str) -> list[Path]:
    results: list[Path] = []
    for path in REPO_ROOT.rglob(f'*{suffix}'):
        if any(part in SKIP_DIRS for part in path.relative_to(REPO_ROOT).parts):
            continue
        results.append(path)
    return sorted(results)


def check_py_compile() -> bool:
    """Compile every Python source file without writing bytecode caches."""
    targets = _walk_files('.py')

    print(f'[check] py_compile: {len(targets)} files')
    failed: list[str] = []
    for target in targets:
        try:
            source = target.read_bytes()
            compile(source, str(target), 'exec')
        except (OSError, SyntaxError) as exc:
            failed.append(f'{target.relative_to(REPO_ROOT)}: {exc}')

    if failed:
        print('[FAIL] py_compile errors:')
        for entry in failed:
            print(f'  - {entry}')
        return False
    print('[ok]   py_compile')
    return True


def check_ruff() -> bool:
    """Run ruff on every Python source file."""
    targets = _walk_files('.py')
    print(f'[check] ruff: {len(targets)} files')

    cmd = ['ruff', 'check', *[str(t) for t in targets]]
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        print('[FAIL] ruff not on PATH; run checks with `mise run check`')
        return False
    except subprocess.CalledProcessError:
        print('[FAIL] ruff reported issues')
        return False
    print('[ok]   ruff')
    return True


def check_shellcheck() -> bool:
    """Run ShellCheck over the topic shell configuration.

    Scoped to ``.sh`` and ``.bash`` deliberately:

    * ``.zsh`` files are excluded because ShellCheck has no zsh dialect
      and cannot check them at all.
    * ``*.symlink`` files fall outside these two suffixes and so are
      excluded for free. That is deliberate, not an oversight: the shell
      entry points (``bashrc.symlink`` and friends) source their topic
      files through a computed path, which is SC1090 by construction —
      real, but not fixable, so gating on it would only teach us to
      ignore the check.

    ``.sh`` files are sourced by both bash and zsh, so they are checked
    as bash: of the two real target shells it is the stricter one that
    ShellCheck can actually model. POSIX ``-s sh`` would be wrong here —
    it rejects ``local``, which both target shells support.
    """
    targets = sorted(_walk_files('.sh') + _walk_files('.bash'))
    print(f'[check] shellcheck: {len(targets)} files')
    if not targets:
        print('[ok]   shellcheck (no shell files)')
        return True

    cmd = ['shellcheck', '--shell=bash', *[str(t) for t in targets]]
    try:
        subprocess.run(cmd, check=True, cwd=REPO_ROOT)
    except FileNotFoundError:
        print('[FAIL] shellcheck not on PATH; run checks with `mise run check`')
        return False
    except subprocess.CalledProcessError:
        print('[FAIL] shellcheck reported issues')
        return False
    print('[ok]   shellcheck')
    return True


def check_actionlint() -> bool:
    """Lint the GitHub Actions workflows with actionlint.

    actionlint delegates ``run:`` block linting to ShellCheck and
    **silently skips it, still exiting 0, when ShellCheck is not on
    PATH**. That is why ``shellcheck`` runs first in ``CHECKS`` and is a
    hard failure: without it this check quietly covers less than it
    appears to.
    """
    workflows = REPO_ROOT / '.github' / 'workflows'
    if not workflows.is_dir():
        print('[ok]   actionlint (no workflows)')
        return True
    print('[check] actionlint: .github/workflows')

    try:
        subprocess.run(['actionlint'], check=True, cwd=REPO_ROOT)
    except FileNotFoundError:
        print('[FAIL] actionlint not on PATH; run checks with `mise run check`')
        return False
    except subprocess.CalledProcessError:
        print('[FAIL] actionlint reported issues')
        return False
    print('[ok]   actionlint')
    return True


def _machine_error(errors, source, path, message):
    errors.append(f'{source}:{path}: {message}')


def validate_machine_data(data, source, *, require_git=False) -> list[str]:
    """Validate one machine override and return human-readable errors."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return [f'{source}: root must be an object']

    def object_at(value, path, allowed):
        if not isinstance(value, dict):
            _machine_error(errors, source, path, 'must be an object')
            return False
        for key in value.keys() - allowed:
            _machine_error(errors, source, f'{path}.{key}', 'unknown key')
        return True

    object_at(data, '$', {'git', 'ssh', 'claude', 'providers'})
    if require_git and 'git' not in data:
        _machine_error(errors, source, '$.git', 'required key missing')

    if 'git' in data and object_at(data['git'], '$.git', {'user'}):
        git = data['git']
        if require_git and 'user' not in git:
            _machine_error(errors, source, '$.git.user', 'required key missing')
        if 'user' in git and object_at(
            git['user'], '$.git.user', {'name', 'email', 'signingkey'}
        ):
            user = git['user']
            if require_git:
                for key in ('name', 'email', 'signingkey'):
                    if key not in user:
                        _machine_error(
                            errors, source, f'$.git.user.{key}', 'required key missing'
                        )
            for key in ('name', 'email'):
                if key in user and not isinstance(user[key], str):
                    _machine_error(errors, source, f'$.git.user.{key}', 'must be a string')
            if 'signingkey' in user and not isinstance(user['signingkey'], (str, type(None))):
                _machine_error(
                    errors, source, '$.git.user.signingkey', 'must be a string or null'
                )

    if 'claude' in data and object_at(
        data['claude'], '$.claude', {'removeDenyRules'}
    ):
        value = data['claude'].get('removeDenyRules')
        if 'removeDenyRules' in data['claude'] and type(value) is not bool:
            _machine_error(
                errors, source, '$.claude.removeDenyRules', 'must be a boolean'
            )

    if 'ssh' in data and object_at(data['ssh'], '$.ssh', {'aiKey', 'keys'}):
        ssh = data['ssh']
        if 'aiKey' in ssh and not isinstance(ssh['aiKey'], str):
            _machine_error(errors, source, '$.ssh.aiKey', 'must be a string')
        if 'keys' in ssh:
            if not isinstance(ssh['keys'], list):
                _machine_error(errors, source, '$.ssh.keys', 'must be an array')
            else:
                key_fields = {
                    'name': str,
                    'fingerprint': str,
                    'public_key': str,
                    'op_vault': str,
                    'op_account': str,
                    'auth': bool,
                    'sign': bool,
                }
                for index, key_data in enumerate(ssh['keys']):
                    path = f'$.ssh.keys[{index}]'
                    if not object_at(key_data, path, set(key_fields)):
                        continue
                    for key, expected_type in key_fields.items():
                        if key not in key_data:
                            _machine_error(errors, source, f'{path}.{key}', 'required key missing')
                        elif type(key_data[key]) is not expected_type:
                            _machine_error(
                                errors,
                                source,
                                f'{path}.{key}',
                                f'must be a {expected_type.__name__}',
                            )

    if 'providers' in data and object_at(
        data['providers'], '$.providers', {'litellm'}
    ):
        providers = data['providers']
        credential_fields = {'op_account': str, 'op_ref': str}
        for provider in providers:
            path = f'$.providers.{provider}'
            entry = providers[provider]
            if not object_at(entry, path, set(credential_fields)):
                continue
            for key, expected_type in credential_fields.items():
                if key not in entry:
                    _machine_error(errors, source, f'{path}.{key}', 'required key missing')
                elif type(entry[key]) is not expected_type:
                    _machine_error(
                        errors, source, f'{path}.{key}', f'must be a {expected_type.__name__}'
                    )
    return errors


def _deep_merge(base, override):
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def check_machine_configs() -> list[str]:
    """Validate machine schemas and references after applying defaults."""
    machines_dir = REPO_ROOT / 'machines'
    default_path = machines_dir / 'default.json'
    try:
        default = json.loads(default_path.read_text())
    except (OSError, json.JSONDecodeError):
        return []  # The general JSON check reports this with better context.

    errors = validate_machine_data(default, 'machines/default.json', require_git=True)
    for path in sorted(machines_dir.glob('*.json')):
        if path == default_path:
            data = default
        else:
            try:
                data = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            errors.extend(validate_machine_data(data, str(path.relative_to(REPO_ROOT))))

        merged = _deep_merge(default, data)
        merged_git = merged.get('git')
        merged_git = merged_git if isinstance(merged_git, dict) else {}
        merged_user = merged_git.get('user')
        merged_user = merged_user if isinstance(merged_user, dict) else {}
        merged_ssh = merged.get('ssh')
        merged_ssh = merged_ssh if isinstance(merged_ssh, dict) else {}
        merged_keys = merged_ssh.get('keys')
        merged_keys = merged_keys if isinstance(merged_keys, list) else []
        keys_by_name = {}
        for key in merged_keys:
            if not isinstance(key, dict) or not isinstance(key.get('name'), str):
                continue
            key_name = key['name']
            if key_name in keys_by_name:
                _machine_error(
                    errors,
                    str(path.relative_to(REPO_ROOT)),
                    '$.ssh.keys',
                    f'duplicate SSH key name {key_name!r}',
                )
            else:
                keys_by_name[key_name] = key
        references = {
            '$.git.user.signingkey': merged_user.get('signingkey'),
            '$.ssh.aiKey': merged_ssh.get('aiKey'),
        }
        for ref_path, key_name in references.items():
            if not isinstance(key_name, str):
                continue
            if key_name not in keys_by_name:
                _machine_error(
                    errors,
                    str(path.relative_to(REPO_ROOT)),
                    ref_path,
                    f'references unknown SSH key {key_name!r}',
                )
            elif keys_by_name[key_name].get('sign') is not True:
                _machine_error(
                    errors,
                    str(path.relative_to(REPO_ROOT)),
                    ref_path,
                    f'references SSH key {key_name!r} that is not enabled for signing',
                )
    return errors


def check_json() -> bool:
    """Validate every JSON file and all machine configuration semantics."""
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

    failed.extend(check_machine_configs())

    if failed:
        print('[FAIL] JSON parse errors:')
        for entry in failed:
            print(f'  - {entry}')
        return False
    print('[ok]   json')
    return True


def check_tests() -> bool:
    """Run the repository's standard-library unittest suite."""
    print('[check] tests: unittest discover')
    try:
        subprocess.run(
            [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests'],
            check=True,
            cwd=REPO_ROOT,
        )
    except subprocess.CalledProcessError:
        print('[FAIL] unit tests failed')
        return False
    print('[ok]   tests')
    return True


def check_install_dry_run() -> bool:
    """Run `script/install.py --dry-run` to exercise every topic installer."""
    install_py = SCRIPT_DIR / 'install.py'
    print('[check] install.py --dry-run')
    with tempfile.TemporaryDirectory() as temp_dir:
        home = Path(temp_dir) / 'home'
        env = os.environ.copy()
        env.update(
            {
                'HOME': str(home),
                'XDG_CONFIG_HOME': str(home / '.config'),
                'XDG_DATA_HOME': str(home / '.local/share'),
                'XDG_CACHE_HOME': str(home / '.cache'),
                'XDG_STATE_HOME': str(home / '.local/state'),
                # This runner's real hostname is never enrolled in
                # machines/, and installers now fail fast on unenrolled
                # hostnames (see get_machine_config()). Point at
                # machines/default.json itself so the dry run exercises
                # the normal "hostname has a dedicated file" path
                # instead of tripping that check.
                'DOTFILES_MACHINE_HOSTNAME': 'default',
            }
        )
        try:
            subprocess.run(
                [sys.executable, str(install_py), '--dry-run'],
                check=True,
                cwd=REPO_ROOT,
                env=env,
            )
        except subprocess.CalledProcessError:
            print('[FAIL] install.py --dry-run returned non-zero')
            return False
        if home.exists():
            print('[FAIL] install.py --dry-run modified its temporary home')
            return False
    print('[ok]   install.py --dry-run')
    return True


CHECKS = {
    'py_compile': check_py_compile,
    'ruff': check_ruff,
    # shellcheck must precede actionlint: see check_actionlint's docstring.
    'shellcheck': check_shellcheck,
    'actionlint': check_actionlint,
    'json': check_json,
    'tests': check_tests,
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
