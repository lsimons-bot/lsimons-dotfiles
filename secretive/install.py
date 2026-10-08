#!/usr/bin/env python3
"""Installation script for Secretive and the Secure Enclave age plugin.

Secretive (https://github.com/maxgoedjen/secretive) is an SSH agent whose
keys live in the Secure Enclave and are gated by Touch ID. age-plugin-se
lets age encrypt to a Secure Enclave key. age itself comes from the
`toolbelt` topic.

This only installs them. Creating a key, enabling SecretAgent
notifications and registering the key with GitHub stay manual, and the
1Password SSH agent remains the default agent everywhere else.

The Secretive cask writes /Applications and asks for an admin password.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import ensure_package, info, parse_dry_run


def main():
    parse_dry_run()
    info("Installing Secretive and age-plugin-se...")

    ok = ensure_package('Secretive', brew='secretive', cask=True, macos_app='Secretive')
    ok = ensure_package('age-plugin-se', brew='age-plugin-se', command='age-plugin-se') and ok
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
