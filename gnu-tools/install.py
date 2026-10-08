#!/usr/bin/env python3
"""Installation script for GNU userland tools macOS lacks.

* gnu-sed, as `gsed`: GNU sed semantics without BSD sed's `-i ''` quirks.
* watch: re-run a command periodically.

Linux already has both (GNU sed, procps' watch).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import ensure_package, info, parse_dry_run


def main():
    parse_dry_run()
    info("Installing GNU tools (gsed, watch)...")

    ok = ensure_package('gnu-sed', brew='gnu-sed', command='gsed')
    ok = ensure_package('watch', brew='watch', command='watch') and ok
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
