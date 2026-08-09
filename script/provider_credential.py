#!/usr/bin/env python3
"""Print shell variable assignments for a provider's 1Password credential.

Usage:
    provider_credential.py <provider>

Resolves ``providers.<provider>`` for the CURRENT machine (see
``get_machine_config()`` / ``get_provider_credential()`` in helpers.py) and
prints, on stdout, ``eval``-able assignments:

    PROVIDER_CREDENTIAL_OP_ACCOUNT='...'
    PROVIDER_CREDENTIAL_OP_REF='...'

Called at call time (not install time) by shell wrapper functions such as
codex/codex.sh and opencode/opencode.sh, so that credentials resolve from
whichever machine the shell is running on right now.

Fails closed: if the current machine has no (complete) configuration for
<provider>, nothing is printed on stdout, a clear message goes to stderr,
and the process exits non-zero. There is no fallback to another machine's
account/reference.
"""

import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import get_provider_credential


def main(argv):
    if len(argv) != 2:
        print("usage: provider_credential.py <provider>", file=sys.stderr)
        return 2

    provider = argv[1]
    try:
        op_account, op_ref = get_provider_credential(provider)
    except ValueError as exc:
        print(f"provider_credential: {exc}", file=sys.stderr)
        return 1

    print(f"PROVIDER_CREDENTIAL_OP_ACCOUNT={shlex.quote(op_account)}")
    print(f"PROVIDER_CREDENTIAL_OP_REF={shlex.quote(op_ref)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
