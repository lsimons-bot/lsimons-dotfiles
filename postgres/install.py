#!/usr/bin/env python3
"""Installation script for the PostgreSQL 16 client tools (psql, pg_dump, ...).

Installed keg-only and deliberately NOT linked: whatever psql is already
on PATH keeps winning machine-wide. A project that needs this major puts
/opt/homebrew/opt/postgresql@16/bin on PATH for its own tree, e.g. through
its mise.toml `[env] _.path`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import ensure_package, info, parse_dry_run


def main():
    parse_dry_run()
    info("Installing the PostgreSQL 16 client (keg-only)...")

    # No `command=` probe: some other psql on PATH says nothing about this major.
    if not ensure_package('PostgreSQL 16', brew='postgresql@16'):
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
